"""Armazenamento seguro de segredos.

Usa o cofre do sistema via ``keyring`` (no Windows: Gerenciador de Credenciais,
protegido pela conta do usuário/DPAPI). Se nenhum cofre estiver disponível, os
segredos ficam APENAS em memória durante a execução — nunca em texto puro no disco.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)
SERVICE = "xiaomi1c"
ROBOT_TOKEN = "robot_token"
CLOUD_SESSION = "cloud_session"


class SecretStore:
    def __init__(self, use_keyring: bool = True):
        self._mem: dict[str, str] = {}
        self._kr = None
        if use_keyring:
            try:
                import keyring
                from keyring.backends import fail

                if isinstance(keyring.get_keyring(), fail.Keyring):
                    raise RuntimeError("nenhum backend de cofre disponível")
                self._kr = keyring
            except Exception as exc:  # noqa: BLE001
                log.warning("Cofre do sistema indisponível (%s); segredos ficarão só em memória.", exc)

    @property
    def persistent(self) -> bool:
        return self._kr is not None

    def get(self, name: str) -> str | None:
        if self._kr is not None:
            try:
                return self._kr.get_password(SERVICE, name)
            except Exception as exc:  # noqa: BLE001
                log.error("Falha ao ler segredo '%s' do cofre: %s", name, exc)
        return self._mem.get(name)

    def set(self, name: str, value: str) -> None:
        if self._kr is not None:
            self._kr.set_password(SERVICE, name, value)
        else:
            self._mem[name] = value

    def delete(self, name: str) -> None:
        self._mem.pop(name, None)
        if self._kr is not None:
            try:
                self._kr.delete_password(SERVICE, name)
            except Exception:  # noqa: BLE001 - já inexistente
                pass

    def has(self, name: str) -> bool:
        return bool(self.get(name))
