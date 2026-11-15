"""Transporte UDP do miIO: handshake, envio com retentativas e descoberta na rede."""
from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

from .miio_protocol import HELLO_PACKET, ProtocolError, build_packet, parse_header, parse_packet, parse_token

log = logging.getLogger(__name__)

PORT = 54321


class DeviceError(Exception):
    """Erro devolvido pelo próprio robô (campo ``error`` da resposta)."""

    def __init__(self, error: Any):
        self.error = error
        code = error.get("code") if isinstance(error, dict) else None
        msg = error.get("message") if isinstance(error, dict) else str(error)
        super().__init__(f"Robô respondeu com erro {code}: {msg}")
        self.code = code


class CommunicationError(Exception):
    """Timeout ou falha de rede ao falar com o robô."""


@dataclass
class DiscoveredDevice:
    ip: str
    device_id: int
    stamp: int


def discover(timeout: float = 3.0, address: str = "255.255.255.255") -> list[DiscoveredDevice]:
    """Envia pacotes *hello* (broadcast) e lista os dispositivos miIO que respondem.

    É uma operação somente-leitura: o hello não altera nada no dispositivo.
    O hello **não** revela o modelo; isso exige o token (``miIO.info``).
    """
    found: dict[str, DiscoveredDevice] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)
    try:
        for _ in range(3):
            sock.sendto(HELLO_PACKET, (address, PORT))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, (ip, _port) = sock.recvfrom(4096)
            except socket.timeout:
                continue
            try:
                header = parse_header(data)
            except ProtocolError:
                continue
            if ip not in found:
                found[ip] = DiscoveredDevice(ip=ip, device_id=header.device_id, stamp=header.stamp)
                log.info("Dispositivo miIO encontrado em %s (did=%s)", ip, header.device_id)
    finally:
        sock.close()
    return list(found.values())


class MiioTransport:
    """Cliente miIO síncrono e thread-safe para um único dispositivo."""

    def __init__(self, ip: str, token_hex: str, timeout: float = 5.0, retries: int = 3):
        self.ip = ip
        self._token = parse_token(token_hex)
        self.timeout = timeout
        self.retries = retries
        self._lock = threading.Lock()
        self._device_id: int | None = None
        self._stamp_base = 0
        self._stamp_at = 0.0
        self._msg_id = int(time.time()) % 10000 * 10

    # ------------------------------------------------------------------ internals
    def _socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(self.timeout)
        return s

    def handshake(self) -> int:
        s = self._socket()
        try:
            s.sendto(HELLO_PACKET, (self.ip, PORT))
            data, _ = s.recvfrom(4096)
        except (socket.timeout, OSError) as exc:
            raise CommunicationError(f"Sem resposta ao handshake de {self.ip}: {exc}") from exc
        finally:
            s.close()
        header = parse_header(data)
        self._device_id = header.device_id
        self._stamp_base = header.stamp
        self._stamp_at = time.monotonic()
        log.debug("Handshake OK com %s (did=%s, stamp=%s)", self.ip, header.device_id, header.stamp)
        return header.device_id

    def _stamp(self) -> int:
        return self._stamp_base + int(time.monotonic() - self._stamp_at) + 1

    def _next_id(self) -> int:
        self._msg_id = (self._msg_id + 1) % 0xFFFF or 1
        return self._msg_id

    # ------------------------------------------------------------------ public
    def send(self, method: str, params: Any = None) -> Any:
        """Envia um comando e devolve ``result``. Faz handshake e retentativas."""
        with self._lock:
            last_exc: Exception | None = None
            for attempt in range(1, self.retries + 1):
                try:
                    if self._device_id is None or attempt > 1:
                        self.handshake()
                    return self._send_once(method, params)
                except DeviceError:
                    raise
                except (CommunicationError, ProtocolError, OSError) as exc:
                    last_exc = exc
                    log.warning("Falha na tentativa %d/%d de '%s': %s", attempt, self.retries, method, exc)
                    time.sleep(min(0.5 * attempt, 2.0))
            raise CommunicationError(f"Falha após {self.retries} tentativas: {last_exc}")

    def _send_once(self, method: str, params: Any) -> Any:
        assert self._device_id is not None
        msg_id = self._next_id()
        payload = {"id": msg_id, "method": method, "params": params if params is not None else []}
        packet = build_packet(payload, self._token, self._device_id, self._stamp())
        log.debug("-> %s %s", method, params)
        s = self._socket()
        try:
            s.sendto(packet, (self.ip, PORT))
            while True:
                data, _ = s.recvfrom(16384)
                _header, resp = parse_packet(data, self._token)
                if resp is None:
                    continue
                if resp.get("id") != msg_id:
                    log.debug("Ignorando resposta com id %s (esperado %s)", resp.get("id"), msg_id)
                    continue
                break
        except socket.timeout as exc:
            raise CommunicationError(f"Timeout aguardando resposta de '{method}'") from exc
        finally:
            s.close()
        log.debug("<- %s", resp)
        if "error" in resp:
            raise DeviceError(resp["error"])
        return resp.get("result")
