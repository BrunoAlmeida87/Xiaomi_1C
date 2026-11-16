"""API REST + WebSocket local (FastAPI).

Segurança da API local:
* escuta apenas em 127.0.0.1 por padrão;
* rejeita ``Host`` diferente de localhost (proteção contra DNS rebinding);
* toda requisição que altera estado exige o cabeçalho ``X-Xiaomi1C: 1`` — um site
  externo não consegue enviá-lo sem CORS, que não é habilitado (proteção CSRF);
* segredos (token, sessão da Cloud) nunca são devolvidos pela API.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..cloud.client import SERVERS, CloudError, QrLogin
from ..robot.commands import CommandRejected
from ..robot.transport import CommunicationError, DeviceError, discover
from ..secrets_store import CLOUD_SESSION, ROBOT_TOKEN
from ..services.core import AppCore, NotConfigured

log = logging.getLogger(__name__)
CLIENT_HEADER = "x-xiaomi1c"
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver", "[::1]"}
_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_IP_RE = re.compile(r"^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$")


class CommandBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class VerifyBody(BaseModel):
    worked: bool
    notes: str = ""


class RegionBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str
    data: dict[str, Any]


class DraftBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str
    data: dict[str, Any]


class SettingsBody(BaseModel):
    mode: str | None = None
    robot_ip: str | None = None
    allow_experimental: bool | None = None
    poll_interval_s: float | None = Field(default=None, ge=1, le=300)
    auto_map_refresh: bool | None = None
    map_refresh_interval_s: float | None = Field(default=None, ge=15, le=3600)


class ImportBody(BaseModel):
    did: str
    server: str


def create_app(core: AppCore, static_dir: Path | None = None, lifespan=None) -> FastAPI:
    app = FastAPI(title="Xiaomi 1C Control", version="0.1.0", lifespan=lifespan)
    qr_state: dict[str, Any] = {"login": None}

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception):
        log.error("Erro interno não tratado", exc_info=exc)
        return JSONResponse({"detail": f"Erro interno ({type(exc).__name__}): {exc}. "
                                       "Detalhes completos em %LOCALAPPDATA%\\Xiaomi1C\\logs\\xiaomi1c.log"},
                            status_code=500)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            return JSONResponse({"detail": "Host não permitido"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CLIENT_HEADER) != "1":
            return JSONResponse({"detail": f"Cabeçalho {CLIENT_HEADER} ausente"}, status_code=403)
        return await call_next(request)

    def guarded(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotConfigured as exc:
            raise HTTPException(409, str(exc)) from exc
        except CommandRejected as exc:
            raise HTTPException(400 if exc.reason in ("invalid", "unknown") else 403,
                                {"message": str(exc), "reason": exc.reason}) from exc
        except DeviceError as exc:
            raise HTTPException(502, f"O robô recusou o comando: {exc}") from exc
        except (CommunicationError, OSError) as exc:
            raise HTTPException(504, f"Falha de comunicação com o robô: {exc}") from exc
        except CloudError as exc:
            raise HTTPException(502, f"Xiaomi Cloud: {exc}") from exc
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - devolver erro legível em vez de 500 em texto
            log.exception("Erro inesperado em %s", getattr(fn, "__name__", fn))
            raise HTTPException(500, f"Erro interno ({type(exc).__name__}): {exc}. Detalhes no log: "
                                     "%LOCALAPPDATA%\\Xiaomi1C\\logs\\xiaomi1c.log") from exc

    async def run(fn, *args, **kwargs):
        return await asyncio.to_thread(guarded, fn, *args, **kwargs)

    # ------------------------------------------------------------------ estado / configuração
    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/state")
    def state():
        s = core.settings
        return {
            "simulated": core.simulated,
            "settings": {"mode": s.mode, "robot_ip": s.robot_ip, "robot_did": s.robot_did, "cloud_server": s.cloud_server,
                         "allow_experimental": s.allow_experimental, "poll_interval_s": s.poll_interval_s,
                         "auto_map_refresh": s.auto_map_refresh, "map_refresh_interval_s": s.map_refresh_interval_s},
            "connection": core.connection,
            "has_token": core.secrets.has(ROBOT_TOKEN),
            "has_cloud_session": core.secrets.has(CLOUD_SESSION),
            "secrets_persistent": core.secrets.persistent,
            "cloud_servers": SERVERS,
        }

    @app.put("/api/settings")
    def update_settings(body: SettingsBody):
        changes = body.model_dump(exclude_none=True)
        if "robot_ip" in changes and changes["robot_ip"] and not _IP_RE.match(changes["robot_ip"]):
            raise HTTPException(400, "IP inválido")
        if "mode" in changes and changes["mode"] not in ("simulator", "real"):
            raise HTTPException(400, "Modo inválido")
        reconnect = any(k in changes and changes[k] != getattr(core.settings, k) for k in ("mode", "robot_ip"))
        core.settings_store.update(**changes)
        if reconnect:
            core.reconfigure()
        return state()

    @app.put("/api/secrets/token")
    def set_token(token: str = Body(..., embed=True)):
        if not _TOKEN_RE.match(token.strip()):
            raise HTTPException(400, "O token deve ter 32 caracteres hexadecimais")
        core.secrets.set(ROBOT_TOKEN, token.strip().lower())
        core.reconfigure()
        return {"has_token": True}

    @app.delete("/api/secrets/token")
    def delete_token():
        core.secrets.delete(ROBOT_TOKEN)
        core.reconfigure()
        return {"has_token": False}

    @app.post("/api/discover")
    async def discover_devices():
        devices = await asyncio.to_thread(discover, 3.0)
        return [{"ip": d.ip, "device_id": d.device_id} for d in devices]

    # ------------------------------------------------------------------ robô
    @app.get("/api/device/info")
    async def device_info():
        robot = await run(core.require_robot)
        info = await run(robot.info)
        return {**info, "simulated": robot.simulated}

    @app.get("/api/status")
    async def status():
        if core.status is None:
            await run(core.require_robot)
            await asyncio.to_thread(core.poll_once)
        if core.status is None:
            raise HTTPException(504, core.connection.get("error") or "Sem resposta do robô")
        return core.status

    @app.get("/api/capabilities")
    def capabilities():
        return core.capabilities()

    @app.post("/api/commands/{command_id}")
    async def command(command_id: str, body: CommandBody):
        res = await run(core.execute, command_id, body.params, body.confirm)
        return {"command": res.command, "ok": res.ok, "simulated": res.simulated, "response": res.response, "sent": res.sent,
                "note": "code 0 significa que o robô ACEITOU o comando; confirme visualmente se ele executou."}

    @app.post("/api/commands/{command_id}/verify")
    def verify(command_id: str, body: VerifyBody):
        if core.simulated:
            raise HTTPException(400, "Verificações físicas só valem com o robô real")
        fw = ((core.db.latest_probe(False) or {}).get("info") or {}).get("fw_ver")
        core.db.set_verification(command_id, body.worked, body.notes, fw)
        return {"ok": True}

    @app.post("/api/probe")
    async def run_probe():
        return await run(core.run_probe)

    @app.get("/api/probe/latest")
    def latest_probe():
        return core.db.latest_probe(core.simulated)

    # ------------------------------------------------------------------ mapa
    @app.get("/api/map")
    async def get_map():
        if core.latest_map is None:
            return await run(core.refresh_map)
        return core.latest_map

    @app.post("/api/map/refresh")
    async def refresh_map():
        return await run(core.refresh_map)

    @app.get("/api/maps")
    def list_maps():
        return core.db.maps()

    @app.get("/api/maps/{map_id}")
    def get_saved_map(map_id: int):
        try:
            return core.load_map(map_id)
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(404, "Mapa não encontrado") from exc

    @app.put("/api/rooms/{segment_id}/name")
    def rename_room(segment_id: int, name: str = Body(..., embed=True)):
        core.db.set_room_name(segment_id, name.strip()[:60])
        if core.latest_map:
            for r in core.latest_map["rooms"]:
                if r["id"] == segment_id:
                    r["name"] = name.strip()[:60]
        return {"ok": True, "stored": "somente neste aplicativo (o robô não recebe nomes)"}

    # ------------------------------------------------------------------ regiões e rascunhos
    @app.get("/api/regions")
    def regions():
        return core.db.regions()

    @app.post("/api/regions")
    def create_region(body: RegionBody):
        try:
            return {"id": core.db.save_region(body.name, body.kind, body.data)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/api/regions/{rid}")
    def update_region(rid: int, body: RegionBody):
        try:
            return {"id": core.db.save_region(body.name, body.kind, body.data, rid)}
        except KeyError as exc:
            raise HTTPException(404, "Região não encontrada") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/api/regions/{rid}")
    def delete_region(rid: int):
        if not core.db.delete_region(rid):
            raise HTTPException(404, "Região não encontrada")
        return {"ok": True}

    @app.get("/api/drafts")
    def drafts():
        return core.db.drafts()

    @app.post("/api/drafts")
    def create_draft(body: DraftBody):
        try:
            return {"id": core.db.save_draft(body.name, body.kind, body.data), "robot_recognized": False}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/api/drafts/{did}")
    def delete_draft(did: int):
        if not core.db.delete_draft(did):
            raise HTTPException(404, "Rascunho não encontrado")
        return {"ok": True}

    # ------------------------------------------------------------------ histórico
    @app.get("/api/history/snapshots")
    def snapshots(since: float = 0, limit: int = 2000):
        return core.db.snapshots(since=since, limit=min(limit, 10000), simulated=core.simulated)

    @app.get("/api/history/sessions")
    def sessions(limit: int = 200):
        return core.db.sessions(limit=min(limit, 1000))

    @app.get("/api/audit")
    def audit(limit: int = 200):
        return core.db.audit(limit=min(limit, 1000))

    # ------------------------------------------------------------------ Xiaomi Cloud
    @app.post("/api/cloud/qr/start")
    async def qr_start():
        login = QrLogin()
        try:
            info = await asyncio.to_thread(login.start)
            image = await asyncio.to_thread(login.qr_image)
        except (CloudError, OSError) as exc:
            raise HTTPException(502, f"Não foi possível iniciar o login: {exc}") from exc
        qr_state["login"] = login

        def done(session):
            core.secrets.set(CLOUD_SESSION, session.to_json())
            log.info("Login na Xiaomi Cloud concluído (sessão guardada no cofre)")

        login.wait_in_background(done)
        return {"login_url": info["login_url"], "timeout": info["timeout"],
                "qr_png": "data:image/png;base64," + base64.b64encode(image).decode()}

    @app.get("/api/cloud/qr/status")
    def qr_status():
        login: QrLogin | None = qr_state["login"]
        return {"state": login.state if login else "idle", "error": login.error if login else None,
                "has_cloud_session": core.secrets.has(CLOUD_SESSION)}

    @app.delete("/api/cloud/session")
    def cloud_logout():
        core.secrets.delete(CLOUD_SESSION)
        return {"ok": True}

    @app.get("/api/cloud/devices")
    async def cloud_devices(server: str | None = None):
        cloud = await run(core.cloud)
        servers = [server] if server else None
        devices = await run(cloud.find_devices, servers)
        return [{**{k: v for k, v in d.items() if k != "token"}, "has_token": bool(d.get("token")),
                 "is_1c": d.get("model") == "dreame.vacuum.mc1808"} for d in devices]

    @app.post("/api/cloud/devices/import")
    async def import_device(body: ImportBody):
        if body.server not in SERVERS:
            raise HTTPException(400, "Servidor inválido")
        cloud = await run(core.cloud)
        devices = await run(cloud.list_devices, body.server)
        dev = next((d for d in devices if str(d["did"]) == body.did), None)
        if not dev or not dev.get("token"):
            raise HTTPException(404, "Dispositivo não encontrado na conta")
        core.secrets.set(ROBOT_TOKEN, dev["token"])
        core.settings_store.update(robot_ip=dev.get("localip") or core.settings.robot_ip, robot_did=str(dev["did"]),
                                   cloud_uid=str(dev.get("uid") or core.cloud().session.user_id),
                                   cloud_server=body.server)
        core.reconfigure()
        return {"ok": True, "model": dev.get("model"), "robot_ip": core.settings.robot_ip,
                "note": "Token guardado no cofre do sistema. Mude o modo para 'real' para usar o robô."}

    # ------------------------------------------------------------------ WebSocket
    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        host = (websocket.headers.get("host") or "").rsplit(":", 1)[0]
        origin = websocket.headers.get("origin") or ""
        origin_host = re.sub(r"^https?://", "", origin).rsplit(":", 1)[0]
        if host not in ALLOWED_HOSTS or (origin and origin_host not in ALLOWED_HOSTS):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        def listener(kind: str, payload: Any):
            def put():
                if not queue.full():
                    queue.put_nowait({"type": kind, "data": payload})
            loop.call_soon_threadsafe(put)

        core.subscribe(listener)
        try:
            await websocket.send_text(json.dumps({"type": "connection", "data": core.connection}, default=str))
            if core.status:
                await websocket.send_text(json.dumps({"type": "status", "data": core.status}, default=str))
            while True:
                msg = await queue.get()
                await websocket.send_text(json.dumps(msg, default=str))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            core.unsubscribe(listener)

    # ------------------------------------------------------------------ frontend estático
    if static_dir and static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            f = static_dir / path
            if path and f.is_file() and static_dir in f.resolve().parents:
                return FileResponse(f)
            return FileResponse(static_dir / "index.html")

    return app
