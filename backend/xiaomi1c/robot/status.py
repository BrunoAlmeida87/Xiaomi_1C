"""Normalização do status e diagnóstico (probe) somente-leitura."""
from __future__ import annotations

import logging
import time
from typing import Any

from .device import MAX_PROPS_PER_REQUEST, RobotBackend
from .spec_1c import ERROR_CODES, PROPS_BY_KEY, describe_value

log = logging.getLogger(__name__)


def normalize_status(raw: dict[str, dict[str, Any]], simulated: bool) -> dict[str, Any]:
    """Converte o resultado de ``read_props`` em um status amigável à interface."""
    values: dict[str, Any] = {}
    props: list[dict[str, Any]] = []
    for key, item in raw.items():
        prop = PROPS_BY_KEY[key]
        ok = item.get("code") == 0
        value = item.get("value") if ok else None
        values[key] = value
        props.append({
            "key": key, "siid": prop.siid, "piid": prop.piid, "label": prop.label, "unit": prop.unit,
            "code": item.get("code"), "value": value, "display": describe_value(prop, value) if ok else None,
            "evidence": prop.evidence.value, "notes": prop.notes,
        })
    fault = values.get("device_fault")
    area = values.get("cleaning_area")
    if area is None:
        area = values.get("cleaning_area_18_3")
    return {
        "simulated": simulated,
        "timestamp": time.time(),
        "battery": values.get("battery_level"),
        "charging_state": values.get("charging_state"),
        "charging_label": describe_value(PROPS_BY_KEY["charging_state"], values.get("charging_state")),
        "status": values.get("device_status"),
        "status_label": describe_value(PROPS_BY_KEY["device_status"], values.get("device_status")),
        "mode": values.get("operating_mode"),
        "mode_label": describe_value(PROPS_BY_KEY["operating_mode"], values.get("operating_mode")),
        "error": fault,
        "error_name": ERROR_CODES.get(fault, (None, None))[0] if isinstance(fault, int) else None,
        "error_label": ERROR_CODES.get(fault, (None, f"Código desconhecido ({fault})"))[1] if isinstance(fault, int) else None,
        "fan_speed": values.get("fan_speed"),
        "water_flow": values.get("water_flow"),
        "cleaning_time_min": values.get("cleaning_time"),
        "cleaning_area_m2": area,
        "total_clean_time_min": values.get("total_clean_time"),
        "total_clean_count": values.get("total_clean_times"),
        "total_clean_area_m2": values.get("total_clean_area"),
        "consumables": {
            "main_brush": {"percent": values.get("main_brush_life"), "hours_left": values.get("main_brush_left")},
            "side_brush": {"percent": values.get("side_brush_life"), "hours_left": values.get("side_brush_left")},
            "filter": {"percent": values.get("filter_life"), "hours_left": values.get("filter_left")},
        },
        "volume": values.get("volume"),
        "dnd": {"enabled": values.get("dnd_enabled"), "start": values.get("dnd_start"), "stop": values.get("dnd_stop")},
        "properties": sorted(props, key=lambda p: (p["siid"], p["piid"])),
    }


def probe(robot: RobotBackend, max_siid: int = 30, max_piid: int = 25, delay: float = 0.15) -> dict[str, Any]:
    """Varredura SOMENTE-LEITURA (get_properties) de siid×piid.

    Serve para confirmar tecnicamente quais propriedades o seu firmware expõe.
    Não envia nenhuma ação nem escrita.
    """
    found: list[dict[str, Any]] = []
    errors: dict[str, int] = {}
    info: dict[str, Any] = {}
    try:
        info = robot.info()
    except Exception as exc:  # noqa: BLE001 - registrar e seguir
        info = {"error": str(exc)}
    for siid in range(1, max_siid + 1):
        items = [{"did": f"{siid}.{piid}", "siid": siid, "piid": piid} for piid in range(1, max_piid + 1)]
        for i in range(0, len(items), MAX_PROPS_PER_REQUEST):
            try:
                res = robot.get_raw_properties(items[i : i + MAX_PROPS_PER_REQUEST])
            except Exception as exc:  # noqa: BLE001
                log.warning("Probe siid %s falhou: %s", siid, exc)
                continue
            for r in res:
                code = r.get("code")
                if code == 0:
                    found.append({"siid": r["siid"], "piid": r["piid"], "value": r.get("value")})
                else:
                    errors[str(code)] = errors.get(str(code), 0) + 1
            if delay:
                time.sleep(delay)
    known = {(p.siid, p.piid): p.key for p in PROPS_BY_KEY.values()}
    for f in found:
        f["known_as"] = known.get((f["siid"], f["piid"]))
    return {
        "timestamp": time.time(),
        "simulated": robot.simulated,
        "info": info,
        "model_confirmed": info.get("model") == "dreame.vacuum.mc1808",
        "readable": found,
        "unknown_readable": [f for f in found if not f["known_as"]],
        "error_codes": errors,
    }
