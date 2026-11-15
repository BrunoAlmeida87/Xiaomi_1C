"""Montagem da aplicação (core + API) e execução do servidor local."""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from .api.app import create_app
from .logsetup import setup_logging
from .secrets_store import SecretStore
from .services.core import AppCore
from .settings import SettingsStore, data_dir
from .storage.db import Database

log = logging.getLogger(__name__)


def frontend_dir() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False):  # executável PyInstaller
        candidates.append(Path(getattr(sys, "_MEIPASS", ".")) / "frontend")
    candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
    return next((c for c in candidates if (c / "index.html").exists()), None)


def build(start_poller: bool = True):
    ddir = data_dir()
    setup_logging(ddir / "logs")
    core = AppCore(SettingsStore(), SecretStore(), Database(ddir / "xiaomi1c.db"), ddir)

    @asynccontextmanager
    async def lifespan(_app):
        if start_poller:
            core.start()
        log.info("Xiaomi 1C Control iniciado (modo=%s, dados=%s)", core.settings.mode, ddir)
        yield
        core.stop()

    return core, create_app(core, frontend_dir(), lifespan=lifespan)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    _core, app = build()
    uvicorn.run(app, host=host, port=port, log_level="info")
