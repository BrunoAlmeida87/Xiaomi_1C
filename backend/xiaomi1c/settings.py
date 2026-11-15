"""Configuração NÃO sensível (JSON) e diretórios de dados.

Segredos (token do robô, sessão da Cloud) ficam em ``secrets_store`` — nunca aqui.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("XIAOMI1C_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Xiaomi1C"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "xiaomi1c"
    base.mkdir(parents=True, exist_ok=True)
    (base / "maps").mkdir(exist_ok=True)
    (base / "logs").mkdir(exist_ok=True)
    return base


@dataclass
class Settings:
    mode: str = "simulator"  # "simulator" | "real"
    robot_ip: str = ""
    robot_did: str = ""
    cloud_server: str = ""
    cloud_uid: str = ""
    allow_experimental: bool = False
    poll_interval_s: float = 5.0
    auto_map_refresh: bool = False  # baixar mapa da Cloud automaticamente
    map_refresh_interval_s: float = 60.0  # só durante limpeza, se auto_map_refresh
    sim_time_scale: float = 10.0


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "config.json")
        self._lock = threading.Lock()
        self.settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                names = {f.name for f in fields(Settings)}
                return Settings(**{k: v for k, v in raw.items() if k in names})
            except (OSError, ValueError, TypeError):
                pass
        return Settings()

    def update(self, **changes) -> Settings:
        with self._lock:
            names = {f.name for f in fields(Settings)}
            for k, v in changes.items():
                if k not in names:
                    raise KeyError(f"Configuração desconhecida: {k}")
                setattr(self.settings, k, v)
            if self.settings.mode not in ("simulator", "real"):
                raise ValueError("mode deve ser 'simulator' ou 'real'")
            self.path.write_text(json.dumps(asdict(self.settings), indent=2), encoding="utf-8")
            return self.settings
