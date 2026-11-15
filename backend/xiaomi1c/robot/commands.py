"""Executor de comandos com travas de segurança.

Regras (seção 6 do projeto):
* comandos que movem o robô ou alteram configurações exigem ``confirm=True``;
* comandos ``experimental`` exigem, além disso, que o usuário habilite
  explicitamente "permitir comandos experimentais" nas configurações;
* comandos ``not_implemented`` nunca são enviados;
* toda execução é registrada (sem segredos) para auditoria.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from . import spec_1c
from .device import RobotBackend
from .spec_1c import COMMANDS_BY_ID, Evidence

log = logging.getLogger(__name__)
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class CommandRejected(Exception):
    """Comando bloqueado pelas travas de segurança ou parâmetros inválidos."""

    def __init__(self, message: str, reason: str = "invalid"):
        super().__init__(message)
        self.reason = reason


@dataclass
class CommandResult:
    command: str
    ok: bool
    response: Any
    simulated: bool
    sent: list[dict[str, Any]]


class CommandExecutor:
    def __init__(self, robot: RobotBackend, allow_experimental: Callable[[], bool], audit: Callable[[dict], None] | None = None):
        self.robot = robot
        self._allow_experimental = allow_experimental
        self._audit = audit or (lambda _e: None)

    def check(self, command_id: str, confirm: bool) -> spec_1c.Command:
        cmd = COMMANDS_BY_ID.get(command_id)
        if cmd is None:
            raise CommandRejected(f"Comando desconhecido: {command_id}", "unknown")
        if cmd.evidence == Evidence.NOT_IMPLEMENTED or cmd.kind == "none":
            raise CommandRejected(f"'{cmd.label}' não é suportado pelo firmware original: {cmd.notes}", "not_implemented")
        if cmd.evidence == Evidence.EXPERIMENTAL and not self._allow_experimental():
            raise CommandRejected(
                f"'{cmd.label}' é experimental. Habilite 'Permitir comandos experimentais' nas configurações.",
                "experimental_disabled",
            )
        if (cmd.requires_confirmation or cmd.moves_robot) and not confirm:
            raise CommandRejected(f"'{cmd.label}' exige confirmação explícita (confirm=true).", "confirmation_required")
        return cmd

    def execute(self, command_id: str, params: dict[str, Any] | None = None, confirm: bool = False) -> CommandResult:
        params = params or {}
        cmd = self.check(command_id, confirm)
        sent: list[dict[str, Any]] = []

        def action(siid: int, aiid: int, inp: list[dict[str, Any]] | None = None) -> Any:
            sent.append({"type": "action", "siid": siid, "aiid": aiid, "in": inp or []})
            return self.robot.raw_action(siid, aiid, inp)

        def setp(siid: int, piid: int, value: Any) -> Any:
            sent.append({"type": "set", "siid": siid, "piid": piid, "value": value})
            return self.robot.set_raw_property(siid, piid, value)

        try:
            if command_id == "set_fan_speed":
                v = _int_in(params.get("value"), spec_1c.FAN_SPEED, "potência")
                resp = setp(18, 6, v)
            elif command_id == "set_water_flow":
                v = _int_in(params.get("value"), spec_1c.WATER_FLOW, "fluxo de água")
                resp = setp(18, 20, v)
            elif command_id == "set_volume":
                v = int(params.get("value", -1))
                if not 0 <= v <= 100:
                    raise CommandRejected("Volume deve estar entre 0 e 100")
                resp = setp(24, 1, v)
            elif command_id == "set_dnd":
                start, stop = str(params.get("start", "")), str(params.get("stop", ""))
                if not (_HHMM.match(start) and _HHMM.match(stop)):
                    raise CommandRejected("Horários devem estar no formato HH:MM")
                resp = [setp(20, 1, bool(params.get("enabled"))), setp(20, 2, start), setp(20, 3, stop)]
            elif command_id == "clean_zone":
                payload = spec_1c.zone_payload(params.get("zones") or [], int(params.get("repeats", 1)))
                resp = action(18, 1, payload)
            elif command_id == "clean_point":
                zone = spec_1c.point_to_zone(int(params["x"]), int(params["y"]), int(params.get("size", 1000)))
                resp = action(18, 1, spec_1c.zone_payload([zone], int(params.get("repeats", 1))))
            elif command_id == "clean_rooms":
                payload = spec_1c.rooms_payload(
                    [int(r) for r in params.get("rooms") or []],
                    int(params.get("repeats", 1)),
                    int(params.get("fan_speed", 1)),
                )
                resp = action(18, 1, payload)
            elif command_id == "remote_move":
                deg = int(params.get("angle", 0))
                speed = int(params.get("distance", 0))
                if not (-120 <= deg <= 120 and -300 <= speed <= 300):
                    raise CommandRejected("Ângulo deve estar em [-120,120] e distância em [-300,300]")
                resp = action(21, 1, [{"piid": 1, "value": str(deg)}, {"piid": 2, "value": str(speed)}])
            elif cmd.kind == "action":
                assert cmd.siid is not None and cmd.aiid is not None
                resp = action(cmd.siid, cmd.aiid)
            else:
                raise CommandRejected(f"Comando sem implementação: {command_id}", "not_implemented")
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandRejected(f"Parâmetros inválidos: {exc}") from exc

        ok = _response_ok(resp)
        entry = {"command": command_id, "params": params, "sent": sent, "ok": ok, "response": resp,
                 "simulated": self.robot.simulated, "evidence": cmd.evidence.value}
        log.info("Comando %s ok=%s simulado=%s", command_id, ok, self.robot.simulated)
        self._audit(entry)
        return CommandResult(command_id, ok, resp, self.robot.simulated, sent)


def _int_in(value: Any, allowed: dict[int, Any], name: str) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise CommandRejected(f"Valor inválido para {name}") from exc
    if v not in allowed:
        raise CommandRejected(f"Valor de {name} deve ser um de {sorted(allowed)}")
    return v


def _response_ok(resp: Any) -> bool:
    if isinstance(resp, list):
        return all(_response_ok(r) for r in resp)
    if isinstance(resp, dict):
        return resp.get("code") == 0
    return False
