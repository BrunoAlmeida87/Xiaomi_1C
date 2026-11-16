"""Núcleo da aplicação: conexão com o robô, polling com reconexão, histórico e mapas."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..cloud.client import CloudError, CloudSession, XiaomiCloud
from ..maps.dreame_format import MapFormatError, parse_cloud_file
from ..robot import spec_1c
from ..robot.commands import CommandExecutor
from ..robot.device import RealRobot, RobotBackend
from ..robot.simulator import SimulatedRobot
from ..robot.status import normalize_status, probe
from ..robot.transport import CommunicationError, DeviceError
from ..secrets_store import CLOUD_SESSION, ROBOT_TOKEN, SecretStore
from ..settings import SettingsStore
from ..storage.db import Database

log = logging.getLogger(__name__)

CLEANING_STATUSES = {1, 7, 13}  # aspirando, passando pano, manual
ACTIVE_STATUSES = CLEANING_STATUSES | {3, 5}  # + pausado, voltando


class NotConfigured(Exception):
    pass


class SessionTracker:
    """Deriva sessões de limpeza a partir das transições de estado (histórico local)."""

    def __init__(self, db: Database):
        self.db = db
        self.current: int | None = None
        self.last: dict[str, Any] | None = None

    def update(self, s: dict[str, Any]) -> None:
        st = s.get("status")
        if self.current is None and st in CLEANING_STATUSES:
            self.current = self.db.open_session(s["timestamp"], s["simulated"], s.get("mode"), s.get("battery"))
            log.info("Sessão de limpeza iniciada (#%s)", self.current)
        elif self.current is not None and st not in ACTIVE_STATUSES:
            ref = self.last or s
            result = "erro" if st == 4 else "concluída"
            self.db.close_session(self.current, s["timestamp"], ref.get("cleaning_area_m2"),
                                  ref.get("cleaning_time_min"), s.get("battery"), result)
            log.info("Sessão de limpeza encerrada (#%s): %s", self.current, result)
            self.current = None
        if st in ACTIVE_STATUSES:
            self.last = s


class AppCore:
    def __init__(self, settings: SettingsStore, secrets: SecretStore, db: Database, data_dir: Path):
        self.settings_store = settings
        self.secrets = secrets
        self.db = db
        self.data_dir = data_dir
        self._lock = threading.RLock()
        self.robot: RobotBackend | None = None
        self.executor: CommandExecutor | None = None
        self.status: dict[str, Any] | None = None
        self.connection: dict[str, Any] = {"state": "disconnected", "error": None, "since": time.time()}
        self.latest_map: dict[str, Any] | None = None
        self.sessions = SessionTracker(db)
        self._listeners: list[Callable[[str, Any], None]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_map_refresh = 0.0
        self.reconfigure()

    # ------------------------------------------------------------------ eventos
    def subscribe(self, fn: Callable[[str, Any], None]) -> None:
        self._listeners.append(fn)

    def unsubscribe(self, fn: Callable[[str, Any], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _emit(self, kind: str, payload: Any) -> None:
        for fn in list(self._listeners):
            try:
                fn(kind, payload)
            except Exception:  # noqa: BLE001
                log.exception("Listener falhou")

    # ------------------------------------------------------------------ configuração
    @property
    def settings(self):
        return self.settings_store.settings

    @property
    def simulated(self) -> bool:
        return self.settings.mode == "simulator"

    def reconfigure(self) -> None:
        with self._lock:
            s = self.settings
            if s.mode == "simulator":
                self.robot = SimulatedRobot(time_scale=s.sim_time_scale)
            else:
                token = self.secrets.get(ROBOT_TOKEN)
                if not s.robot_ip or not token:
                    self.robot = None
                    self._set_connection("not_configured", "Informe o IP e importe/defina o token do robô")
                else:
                    self.robot = RealRobot(s.robot_ip, token)
            self.executor = (CommandExecutor(self.robot, lambda: self.settings.allow_experimental, self.db.add_audit)
                             if self.robot else None)
            self.status = None
            self.latest_map = None
            self.sessions = SessionTracker(self.db)
            if self.robot:
                self._set_connection("connecting", None)

    def require_robot(self) -> RobotBackend:
        if self.robot is None:
            raise NotConfigured("Robô não configurado (modo real sem IP/token)")
        return self.robot

    def _set_connection(self, state: str, error: str | None) -> None:
        if self.connection.get("state") != state or self.connection.get("error") != error:
            self.connection = {"state": state, "error": error, "since": time.time(), "simulated": self.simulated}
            self._emit("connection", self.connection)

    # ------------------------------------------------------------------ polling
    def poll_once(self) -> dict[str, Any] | None:
        robot = self.robot
        if robot is None:
            return None
        try:
            raw = robot.read_props()
            status = normalize_status(raw, robot.simulated)
        except (CommunicationError, DeviceError, OSError) as exc:
            self._set_connection("offline", str(exc))
            return None
        except Exception as exc:  # noqa: BLE001 - nunca derrubar o polling
            log.exception("Resposta inesperada ao ler o status")
            self._set_connection("offline", f"Resposta inesperada do robô: {type(exc).__name__}: {exc}")
            return None
        self.status = status
        self._set_connection("online", None)
        self.db.add_snapshot(status)
        self.sessions.update(status)
        self._emit("status", status)
        return status

    def _loop(self) -> None:
        backoff = 0.0
        while not self._stop.is_set():
            try:
                st = self.poll_once()
            except Exception:  # noqa: BLE001
                log.exception("Erro no ciclo de atualização")
                st = None
            interval = max(1.0, float(self.settings.poll_interval_s))
            if st is None and self.robot is not None:
                backoff = min(60.0, backoff * 2 if backoff else interval)
                wait = backoff
            else:
                backoff = 0.0
                wait = interval
            if st and self.settings.auto_map_refresh and st.get("status") in ACTIVE_STATUSES:
                if time.time() - self._last_map_refresh > max(15.0, self.settings.map_refresh_interval_s):
                    try:
                        self.refresh_map()
                    except Exception as exc:  # noqa: BLE001
                        log.warning("Atualização automática do mapa falhou: %s", exc)
            if self.simulated and st and st.get("status") in ACTIVE_STATUSES and time.time() - self._last_map_refresh > 3:
                try:
                    self.refresh_map(store=False)
                except Exception:  # noqa: BLE001
                    log.exception("Mapa simulado falhou")
            self._stop.wait(wait)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="robot-poller")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    # ------------------------------------------------------------------ comandos
    def execute(self, command_id: str, params: dict[str, Any], confirm: bool):
        if self.executor is None:
            raise NotConfigured("Robô não configurado")
        result = self.executor.execute(command_id, params, confirm)
        threading.Thread(target=self.poll_once, daemon=True).start()
        return result

    def run_probe(self) -> dict[str, Any]:
        result = probe(self.require_robot(), delay=0 if self.simulated else 0.15)
        self.db.add_probe(result)
        return result

    # ------------------------------------------------------------------ capacidades
    def capabilities(self) -> dict[str, Any]:
        latest = self.db.latest_probe(simulated=False)
        readable = {(r["siid"], r["piid"]) for r in (latest or {}).get("readable", [])}
        firmware = ((latest or {}).get("info") or {}).get("fw_ver")
        verifications = self.db.verifications()

        props = []
        for p in spec_1c.PROPERTIES:
            ev = p.evidence
            if (p.siid, p.piid) in readable:
                ev = spec_1c.Evidence.VERIFIED
            props.append({"key": p.key, "siid": p.siid, "piid": p.piid, "label": p.label, "access": p.access,
                          "evidence": ev.value, "evidence_label": spec_1c.EVIDENCE_LABELS_PT[ev], "base_evidence": p.evidence.value,
                          "sources": list(p.sources), "notes": p.notes, "unit": p.unit})
        cmds = []
        for c in spec_1c.COMMANDS:
            ev = c.evidence
            ver = verifications.get(c.id)
            if ver and ver["worked"] and ev != spec_1c.Evidence.NOT_IMPLEMENTED:
                ev = spec_1c.Evidence.VERIFIED
            cmds.append({"id": c.id, "label": c.label, "evidence": ev.value, "evidence_label": spec_1c.EVIDENCE_LABELS_PT[ev],
                         "base_evidence": c.evidence.value, "sources": list(c.sources), "moves_robot": c.moves_robot,
                         "requires_confirmation": c.requires_confirmation or c.moves_robot, "notes": c.notes,
                         "siid": c.siid, "aiid": c.aiid, "piid": c.piid, "params": c.params_schema, "verification": ver})
        return {"model": spec_1c.MODEL, "probe_available": latest is not None, "probe_firmware": firmware,
                "model_confirmed": (latest or {}).get("model_confirmed"), "properties": props, "commands": cmds,
                "allow_experimental": self.settings.allow_experimental}

    # ------------------------------------------------------------------ mapa
    def cloud(self) -> XiaomiCloud:
        raw = self.secrets.get(CLOUD_SESSION)
        if not raw:
            raise NotConfigured("Sem sessão da Xiaomi Cloud. Faça login por QR code em Configurações.")
        return XiaomiCloud(CloudSession.from_json(raw))

    def refresh_map(self, store: bool = True) -> dict[str, Any]:
        """Obtém o mapa: simulador local, ou Xiaomi Cloud no modo real."""
        robot = self.require_robot()
        ts = time.time()
        if isinstance(robot, SimulatedRobot):
            raw = robot.map_file().encode()
            source = "simulator"
        else:
            s = self.settings
            if not (s.cloud_server and s.cloud_uid and s.robot_did):
                raise NotConfigured("Importe o robô pela Xiaomi Cloud (servidor/uid/did) para baixar o mapa")
            try:
                raw = self.cloud().download_map(s.cloud_server, s.cloud_uid, s.robot_did)
            except CloudError as exc:
                raise NotConfigured(str(exc)) from exc
            source = "cloud"
        try:
            model = parse_cloud_file(raw, source=source)
        except MapFormatError as exc:
            raise NotConfigured(f"Mapa recebido em formato inesperado: {exc}") from exc
        data = model.to_dict()
        names = self.db.room_names()
        sim_names = SimulatedRobot.room_names() if source == "simulator" else {}
        for r in data["rooms"]:
            r["robot_name"] = r["name"]
            r["name"] = names.get(r["id"]) or sim_names.get(r["id"]) or r["name"]
        data.update(simulated=robot.simulated, timestamp=ts)
        if store:
            fname = f"map_{time.strftime('%Y%m%d_%H%M%S', time.localtime(ts))}_{source}.b64"
            (self.data_dir / "maps" / fname).write_bytes(raw)
            data["id"] = self.db.add_map(ts, source, robot.simulated, fname, {
                "width": model.width, "height": model.height, "rooms": len(model.rooms),
                "virtual_walls": len(model.virtual_walls), "no_go": len(model.no_go_areas),
                "has_saved_map": model.has_saved_map})
            self._last_map_refresh = ts
        else:
            self._last_map_refresh = ts
        self.latest_map = data
        self._emit("map", {"timestamp": ts, "id": data.get("id"), "simulated": robot.simulated})
        return data

    def load_map(self, map_id: int) -> dict[str, Any]:
        row = self.db.map_by_id(map_id)
        if not row:
            raise KeyError(map_id)
        raw = (self.data_dir / "maps" / row["file"]).read_bytes()
        data = parse_cloud_file(raw, source=row["source"]).to_dict()
        data.update(simulated=row["simulated"], timestamp=row["ts"], id=row["id"])
        return data
