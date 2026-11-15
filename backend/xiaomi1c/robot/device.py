"""Abstração do robô: implementação real (miIO/MIoT local) e interface comum."""
from __future__ import annotations

import abc
import logging
from typing import Any, Iterable

from .spec_1c import PROPS_BY_KEY, READABLE_PROPS, Prop
from .transport import MiioTransport

log = logging.getLogger(__name__)

# Campos do miIO.info que nunca devem sair do backend.
SENSITIVE_INFO_KEYS = {"token", "ap", "netif"}  # ap/netif contêm SSID/BSSID e IPs; filtramos o essencial
MAX_PROPS_PER_REQUEST = 10  # o 1C rejeita lotes grandes (python-miio usa 10)


def sanitize_info(info: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in info.items() if k not in SENSITIVE_INFO_KEYS}
    ap = info.get("ap") or {}
    netif = info.get("netif") or {}
    if ap:
        out["wifi_rssi"] = ap.get("rssi")
    if netif:
        out["local_ip"] = netif.get("localIp")
    return out


class RobotBackend(abc.ABC):
    """Interface comum entre robô real e simulador."""

    simulated: bool = False

    @abc.abstractmethod
    def info(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def get_raw_properties(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Recebe [{did, siid, piid}] e devolve [{did, siid, piid, code, value?}]."""

    @abc.abstractmethod
    def set_raw_property(self, siid: int, piid: int, value: Any) -> dict[str, Any]: ...

    @abc.abstractmethod
    def raw_action(self, siid: int, aiid: int, params: list[dict[str, Any]] | None = None) -> dict[str, Any]: ...

    # ------------------------------------------------------------ helpers comuns
    def read_props(self, props: Iterable[Prop] = READABLE_PROPS) -> dict[str, dict[str, Any]]:
        props = list(props)
        result: dict[str, dict[str, Any]] = {}
        for i in range(0, len(props), MAX_PROPS_PER_REQUEST):
            chunk = props[i : i + MAX_PROPS_PER_REQUEST]
            req = [{"did": p.key, "siid": p.siid, "piid": p.piid} for p in chunk]
            for item in self.get_raw_properties(req):
                key = item.get("did")
                if key in PROPS_BY_KEY:
                    result[key] = {"code": item.get("code"), "value": item.get("value")}
        return result


class RealRobot(RobotBackend):
    """Robô físico via protocolo local miIO + MIoT (sem Cloud)."""

    simulated = False

    def __init__(self, ip: str, token_hex: str, timeout: float = 5.0):
        self.transport = MiioTransport(ip, token_hex, timeout=timeout)
        self.ip = ip

    def info(self) -> dict[str, Any]:
        return sanitize_info(self.transport.send("miIO.info") or {})

    def get_raw_properties(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.transport.send("get_properties", items) or []

    def set_raw_property(self, siid: int, piid: int, value: Any) -> dict[str, Any]:
        res = self.transport.send("set_properties", [{"did": f"set-{siid}-{piid}", "siid": siid, "piid": piid, "value": value}])
        return res[0] if isinstance(res, list) and res else {"code": None, "raw": res}

    def raw_action(self, siid: int, aiid: int, params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload = {"did": f"call-{siid}-{aiid}", "siid": siid, "aiid": aiid, "in": params or []}
        res = self.transport.send("action", payload)
        return res if isinstance(res, dict) else {"code": None, "raw": res}
