"""Cliente da Xiaomi Cloud — usado SOMENTE para:

1. obter o token local e o IP do robô (uma vez), e
2. baixar o mapa (o firmware original não expõe o mapa pela rede local).

Autenticação preferida: **QR code** escaneado pelo app Xiaomi Home — a senha
nunca passa por este aplicativo. A sessão resultante (``userId``, ``ssecurity``,
``serviceToken``) é guardada no cofre do sistema (Windows Credential Manager).

Fluxo baseado em PiotrMachowski/Xiaomi-cloud-tokens-extractor (``QrCodeXiaomiCloudConnector``)
e no Xiaomi Cloud Map Extractor (``XiaomiCloudVacuumV2.get_map_url``).
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

import requests

from . import crypto

log = logging.getLogger(__name__)

SERVERS = ["cn", "de", "us", "ru", "tw", "sg", "in", "i2"]
_QS = "%3Fsid%3Dxiaomiio%26_json%3Dtrue"
_CALLBACK = "https://sts.api.io.mi.com/sts"


class CloudError(Exception):
    pass


@dataclass
class CloudSession:
    user_id: str
    ssecurity: str
    service_token: str
    server: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "CloudSession":
        return cls(**json.loads(data))


def _to_json(text: str) -> Any:
    return json.loads(text.replace("&&&START&&&", ""))


def _agent() -> str:
    agent_id = "".join(chr(random.randint(65, 69)) for _ in range(13))
    rnd = "".join(chr(random.randint(97, 122)) for _ in range(18))
    return f"{rnd}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201"


def api_url(server: str) -> str:
    if server not in SERVERS:
        raise CloudError(f"Servidor desconhecido: {server}")
    return "https://" + ("" if server == "cn" else f"{server}.") + "api.io.mi.com/app"


class QrLogin:
    """Login por QR code em duas etapas: ``start()`` e ``wait()`` (long polling)."""

    def __init__(self, session: requests.Session | None = None):
        self.http = session or requests.Session()
        self.qr_image_url: str | None = None
        self.login_url: str | None = None
        self._lp_url: str | None = None
        self._timeout = 300
        self.state = "idle"  # idle | waiting | done | error | expired
        self.error: str | None = None
        self.result: CloudSession | None = None

    def start(self) -> dict[str, Any]:
        params = {"_qrsize": "480", "qs": _QS, "callback": _CALLBACK, "_hasLogo": "false", "sid": "xiaomiio",
                  "serviceParam": "", "_locale": "pt_BR", "_dc": str(int(time.time() * 1000))}
        r = self.http.get("https://account.xiaomi.com/longPolling/loginUrl", params=params, timeout=15)
        if r.status_code != 200:
            raise CloudError(f"Falha ao iniciar login por QR (HTTP {r.status_code})")
        data = _to_json(r.text)
        if "qr" not in data:
            raise CloudError("Resposta inesperada ao iniciar login por QR")
        self.qr_image_url, self.login_url, self._lp_url = data["qr"], data["loginUrl"], data["lp"]
        self._timeout = int(data.get("timeout", 300))
        self.state = "waiting"
        return {"qr_image_url": self.qr_image_url, "login_url": self.login_url, "timeout": self._timeout}

    def qr_image(self) -> bytes:
        if not self.qr_image_url:
            raise CloudError("Login por QR não iniciado")
        r = self.http.get(self.qr_image_url, timeout=15)
        r.raise_for_status()
        return r.content

    def wait(self) -> CloudSession:
        """Bloqueia até o usuário escanear o QR no app Xiaomi Home (ou expirar)."""
        if not self._lp_url:
            raise CloudError("Login por QR não iniciado")
        deadline = time.time() + self._timeout
        resp = None
        while time.time() < deadline:
            try:
                resp = self.http.get(self._lp_url, timeout=10)
            except requests.Timeout:
                continue
            except requests.RequestException as exc:
                self.state, self.error = "error", str(exc)
                raise CloudError(f"Erro de rede no long polling: {exc}") from exc
            if resp.status_code == 200:
                break
        if resp is None or resp.status_code != 200:
            self.state = "expired"
            raise CloudError("QR code expirado — gere um novo")
        data = _to_json(resp.text)
        location = data.get("location")
        r = self.http.get(location, headers={"content-type": "application/x-www-form-urlencoded"}, timeout=15)
        token = r.cookies.get("serviceToken")
        if r.status_code != 200 or not token:
            self.state = "error"
            raise CloudError("Não foi possível obter o serviceToken")
        self.result = CloudSession(user_id=str(data["userId"]), ssecurity=data["ssecurity"], service_token=token)
        self.state = "done"
        return self.result

    def wait_in_background(self, on_done) -> threading.Thread:
        def run():
            try:
                on_done(self.wait())
            except CloudError as exc:
                self.error = str(exc)
                log.warning("Login por QR falhou: %s", exc)

        t = threading.Thread(target=run, daemon=True, name="xiaomi-qr-login")
        t.start()
        return t


class XiaomiCloud:
    def __init__(self, session: CloudSession, http: requests.Session | None = None):
        self.session = session
        self.http = http or requests.Session()
        self._agent = _agent()

    def call(self, server: str, path: str, data: dict[str, Any]) -> dict[str, Any]:
        url = api_url(server) + path
        nonce = crypto.generate_nonce()
        snonce = crypto.signed_nonce(self.session.ssecurity, nonce)
        fields = crypto.build_encrypted_params(url, "POST", snonce, nonce,
                                               {"data": json.dumps(data, separators=(",", ":"))},
                                               self.session.ssecurity)
        headers = {"Accept-Encoding": "identity", "User-Agent": self._agent,
                   "Content-Type": "application/x-www-form-urlencoded",
                   "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2", "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4"}
        cookies = {"userId": self.session.user_id, "yetAnotherServiceToken": self.session.service_token,
                   "serviceToken": self.session.service_token, "locale": "pt_BR", "channel": "MI_APP_STORE"}
        try:
            r = self.http.post(url, headers=headers, cookies=cookies, params=fields, timeout=15)
        except requests.RequestException as exc:
            raise CloudError(f"Erro de rede: {exc}") from exc
        if r.status_code == 401:
            raise CloudError("Sessão da Xiaomi Cloud expirada — faça login novamente")
        if r.status_code != 200:
            raise CloudError(f"HTTP {r.status_code} em {path}")
        try:
            return json.loads(crypto.decrypt_rc4(crypto.signed_nonce(self.session.ssecurity, fields["_nonce"]), r.text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise CloudError(f"Resposta indecifrável em {path}") from exc

    def list_devices(self, server: str) -> list[dict[str, Any]]:
        """Lista dispositivos. O campo ``token`` é sensível e NÃO deve sair do backend."""
        resp = self.call(server, "/home/device_list", {"getVirtualModel": False, "getHuamiDevices": 0})
        devices = (resp.get("result") or {}).get("list") or []
        return [{"did": d.get("did"), "name": d.get("name"), "model": d.get("model"), "localip": d.get("localip"),
                 "mac": d.get("mac"), "uid": d.get("uid"), "isOnline": d.get("isOnline"), "token": d.get("token"),
                 "server": server} for d in devices]

    def find_devices(self, servers: list[str] | None = None) -> list[dict[str, Any]]:
        found = []
        for s in servers or SERVERS:
            try:
                found += self.list_devices(s)
            except CloudError as exc:
                log.info("Servidor %s: %s", s, exc)
        return found

    def map_file_url(self, server: str, uid: str, did: str, map_name: str = "0") -> str:
        resp = self.call(server, "/v2/home/get_interim_file_url", {"obj_name": f"{uid}/{did}/{map_name}"})
        url = (resp.get("result") or {}).get("url")
        if not url:
            raise CloudError(f"Mapa não disponível na Cloud (resposta: {resp.get('message') or resp.get('code')})")
        return url

    def download_map(self, server: str, uid: str, did: str) -> bytes:
        url = self.map_file_url(server, uid, did)
        r = self.http.get(url, timeout=30)
        if r.status_code != 200:
            raise CloudError(f"Falha ao baixar o mapa (HTTP {r.status_code})")
        return r.content
