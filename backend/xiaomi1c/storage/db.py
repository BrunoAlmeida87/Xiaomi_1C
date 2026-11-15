"""Persistência local em SQLite (histórico, mapas, regiões, auditoria, diagnósticos)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS status_snapshots (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, simulated INTEGER NOT NULL,
  battery INTEGER, status INTEGER, mode INTEGER, error INTEGER,
  area_m2 REAL, clean_time_min REAL, data TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_ts ON status_snapshots(ts);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY, start_ts REAL NOT NULL, end_ts REAL, simulated INTEGER NOT NULL,
  mode INTEGER, area_m2 REAL, duration_min REAL, start_battery INTEGER, end_battery INTEGER, result TEXT
);
CREATE TABLE IF NOT EXISTS maps (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, source TEXT NOT NULL, simulated INTEGER NOT NULL,
  file TEXT NOT NULL, summary TEXT
);
CREATE TABLE IF NOT EXISTS regions (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
  created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
  robot_recognized INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS room_names (segment_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, command TEXT NOT NULL, ok INTEGER, simulated INTEGER, data TEXT
);
CREATE TABLE IF NOT EXISTS verifications (
  command TEXT PRIMARY KEY, worked INTEGER NOT NULL, notes TEXT, firmware TEXT, ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS probes (id INTEGER PRIMARY KEY, ts REAL NOT NULL, simulated INTEGER, data TEXT NOT NULL);
"""

REGION_KINDS = {"zone", "point", "room_sequence"}
DRAFT_KINDS = {"virtual_wall", "no_go", "no_mop"}


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    def _rows(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("data"), str):
                d["data"] = json.loads(d["data"])
            if isinstance(d.get("summary"), str):
                d["summary"] = json.loads(d["summary"])
            for b in ("simulated", "ok", "robot_recognized"):
                if b in d and d[b] is not None:
                    d[b] = bool(d[b])
            out.append(d)
        return out

    # ---------------------------------------------------------------- histórico
    def add_snapshot(self, s: dict[str, Any]) -> None:
        compact = {k: v for k, v in s.items() if k != "properties"}
        self._exec(
            "INSERT INTO status_snapshots(ts,simulated,battery,status,mode,error,area_m2,clean_time_min,data)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (s["timestamp"], int(s["simulated"]), s.get("battery"), s.get("status"), s.get("mode"), s.get("error"),
             s.get("cleaning_area_m2"), s.get("cleaning_time_min"), json.dumps(compact)),
        )

    def snapshots(self, since: float = 0, limit: int = 2000, simulated: bool | None = None) -> list[dict[str, Any]]:
        q, args = "SELECT id,ts,simulated,battery,status,mode,error,area_m2,clean_time_min FROM status_snapshots WHERE ts>=?", [since]
        if simulated is not None:
            q += " AND simulated=?"
            args.append(int(simulated))
        q += " ORDER BY ts DESC LIMIT ?"
        args.append(limit)
        return list(reversed(self._rows(q, tuple(args))))

    def prune_snapshots(self, keep_days: int = 90) -> None:
        self._exec("DELETE FROM status_snapshots WHERE ts < ?", (time.time() - keep_days * 86400,))

    def open_session(self, start_ts: float, simulated: bool, mode: int | None, battery: int | None) -> int:
        cur = self._exec("INSERT INTO sessions(start_ts,simulated,mode,start_battery) VALUES (?,?,?,?)",
                         (start_ts, int(simulated), mode, battery))
        return int(cur.lastrowid)

    def close_session(self, sid: int, end_ts: float, area: float | None, duration: float | None,
                      battery: int | None, result: str) -> None:
        self._exec("UPDATE sessions SET end_ts=?, area_m2=?, duration_min=?, end_battery=?, result=? WHERE id=?",
                   (end_ts, area, duration, battery, result, sid))

    def sessions(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM sessions ORDER BY start_ts DESC LIMIT ?", (limit,))

    # ---------------------------------------------------------------- mapas
    def add_map(self, ts: float, source: str, simulated: bool, file: str, summary: dict[str, Any]) -> int:
        cur = self._exec("INSERT INTO maps(ts,source,simulated,file,summary) VALUES (?,?,?,?,?)",
                         (ts, source, int(simulated), file, json.dumps(summary)))
        return int(cur.lastrowid)

    def maps(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM maps ORDER BY ts DESC LIMIT ?", (limit,))

    def map_by_id(self, mid: int) -> dict[str, Any] | None:
        rows = self._rows("SELECT * FROM maps WHERE id=?", (mid,))
        return rows[0] if rows else None

    # ---------------------------------------------------------------- regiões salvas
    def save_region(self, name: str, kind: str, data: dict[str, Any], rid: int | None = None) -> int:
        if kind not in REGION_KINDS:
            raise ValueError(f"Tipo de região inválido: {kind}")
        now = time.time()
        if rid is None:
            cur = self._exec("INSERT INTO regions(name,kind,data,created,updated) VALUES (?,?,?,?,?)",
                             (name, kind, json.dumps(data), now, now))
            return int(cur.lastrowid)
        cur = self._exec("UPDATE regions SET name=?, kind=?, data=?, updated=? WHERE id=?",
                         (name, kind, json.dumps(data), now, rid))
        if cur.rowcount == 0:
            raise KeyError(rid)
        return rid

    def regions(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM regions ORDER BY name")

    def delete_region(self, rid: int) -> bool:
        return self._exec("DELETE FROM regions WHERE id=?", (rid,)).rowcount > 0

    # ---------------------------------------------------------------- rascunhos de restrição (só interface)
    def save_draft(self, name: str, kind: str, data: dict[str, Any]) -> int:
        if kind not in DRAFT_KINDS:
            raise ValueError(f"Tipo de restrição inválido: {kind}")
        cur = self._exec("INSERT INTO drafts(name,kind,data,robot_recognized,created) VALUES (?,?,?,0,?)",
                         (name, kind, json.dumps(data), time.time()))
        return int(cur.lastrowid)

    def drafts(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM drafts ORDER BY created")

    def delete_draft(self, did: int) -> bool:
        return self._exec("DELETE FROM drafts WHERE id=?", (did,)).rowcount > 0

    # ---------------------------------------------------------------- nomes de cômodos (só no app)
    def set_room_name(self, segment_id: int, name: str) -> None:
        self._exec("INSERT INTO room_names(segment_id,name) VALUES (?,?) ON CONFLICT(segment_id) DO UPDATE SET name=excluded.name",
                   (segment_id, name))

    def room_names(self) -> dict[int, str]:
        return {r["segment_id"]: r["name"] for r in self._rows("SELECT * FROM room_names")}

    # ---------------------------------------------------------------- auditoria e probes
    def add_audit(self, entry: dict[str, Any]) -> None:
        self._exec("INSERT INTO audit(ts,command,ok,simulated,data) VALUES (?,?,?,?,?)",
                   (time.time(), entry["command"], int(bool(entry.get("ok"))), int(bool(entry.get("simulated"))),
                    json.dumps(entry, default=str)))

    def audit(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,))

    def add_probe(self, result: dict[str, Any]) -> int:
        cur = self._exec("INSERT INTO probes(ts,simulated,data) VALUES (?,?,?)",
                         (result["timestamp"], int(result["simulated"]), json.dumps(result, default=str)))
        return int(cur.lastrowid)

    def latest_probe(self, simulated: bool) -> dict[str, Any] | None:
        rows = self._rows("SELECT * FROM probes WHERE simulated=? ORDER BY ts DESC LIMIT 1", (int(simulated),))
        return rows[0]["data"] if rows else None

    # ---------------------------------------------------------------- verificação física (feita pelo usuário)
    def set_verification(self, command: str, worked: bool, notes: str, firmware: str | None) -> None:
        self._exec("INSERT INTO verifications(command,worked,notes,firmware,ts) VALUES (?,?,?,?,?) "
                   "ON CONFLICT(command) DO UPDATE SET worked=excluded.worked, notes=excluded.notes, "
                   "firmware=excluded.firmware, ts=excluded.ts", (command, int(worked), notes, firmware, time.time()))

    def verifications(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM verifications").fetchall()
        return {r["command"]: {"worked": bool(r["worked"]), "notes": r["notes"], "firmware": r["firmware"], "ts": r["ts"]}
                for r in rows}
