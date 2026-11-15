"""Robô SIMULADO — permite testar toda a interface sem o equipamento.

Responde no mesmo nível "bruto" (siid/piid/aiid) que o robô real, de modo que o
mesmo executor de comandos é exercitado nos dois casos. Todos os dados aqui são
FICTÍCIOS e são marcados como ``simulated: true`` em toda a API.
"""
from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

from ..maps.dreame_format import encode_map
from .device import RobotBackend

# Planta fictícia (mm). Cômodos: (id, nome, x0, y0, x1, y1)
ROOMS = [
    (1, "Sala (simulada)", -1500, -500, 3500, 3500),
    (2, "Cozinha (simulada)", 3500, -500, 6500, 2000),
    (3, "Quarto (simulado)", -1500, 3500, 3500, 6500),
    (4, "Corredor (simulado)", 3500, 2000, 6500, 6500),
]
PIXEL = 50
LEFT, TOP = -2000, -1000
W, H = 180, 160
DOORS = [(3500, 500, 3500, 1500), (1000, 3500, 2000, 3500), (3500, 4500, 3500, 5500), (4500, 2000, 5500, 2000)]
CHARGER = (-1200, 0, 0)


def _cell(x: int, y: int) -> tuple[int, int]:
    return (x - LEFT) // PIXEL, (y - TOP) // PIXEL


def build_pixels() -> bytes:
    px = bytearray(W * H)
    for rid, _n, x0, y0, x1, y1 in ROOMS:
        c0, r0 = _cell(x0, y0)
        c1, r1 = _cell(x1, y1)
        for r in range(r0, r1):
            for c in range(c0, c1):
                edge = r in (r0, r1 - 1) or c in (c0, c1 - 1)
                px[r * W + c] = 0b10 if edge else (rid << 2)
    for x0, y0, x1, y1 in DOORS:
        c0, r0 = _cell(min(x0, x1), min(y0, y1))
        c1, r1 = _cell(max(x0, x1), max(y0, y1))
        for r in range(r0 - 1, r1 + 1):
            for c in range(c0 - 1, c1 + 1):
                if 0 <= r < H and 0 <= c < W and px[r * W + c] == 0b10:
                    px[r * W + c] = 0b01
    return bytes(px)


def _lawnmower(x0: int, y0: int, x1: int, y1: int, step: int = 250) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    y, flip = y0 + step // 2, False
    while y < y1:
        pts += [(x1 - 150, y), (x0 + 150, y)] if flip else [(x0 + 150, y), (x1 - 150, y)]
        y += step
        flip = not flip
    return pts


class SimulatedRobot(RobotBackend):
    simulated = True
    SPEED_MM_S = 300

    def __init__(self, time_scale: float = 10.0):
        self._lock = threading.Lock()
        self.time_scale = time_scale
        self._pixels = build_pixels()
        self._last_tick = time.monotonic()
        self.pose = [CHARGER[0], CHARGER[1], 0]
        self.route: list[tuple[int, int]] = []
        self.trail: list[list[int]] = [[CHARGER[0], CHARGER[1]]]
        self.cleaned_mm2 = 0.0
        self.clean_seconds = 0.0
        self.p: dict[tuple[int, int], Any] = {
            (2, 1): 100, (2, 2): 1, (3, 1): 0, (3, 2): 6, (18, 1): 6, (18, 2): 0, (18, 3): 0, (18, 4): 0,
            (18, 6): 1, (18, 9): 0, (18, 12): 1_600_000_000, (18, 13): 3120, (18, 14): 87, (18, 15): 2950,
            (18, 16): 1_600_000_000, (18, 17): 1, (18, 18): 1, (18, 20): 2,
            (19, 1): "sim", (19, 2): "sim", (19, 3): "sim", (20, 1): False, (20, 2): "22:00", (20, 3): "08:00",
            (23, 1): "sim", (24, 1): 60, (24, 3): "PT", (25, 1): "America/Sao_Paulo",
            (26, 1): 230, (26, 2): 77, (27, 1): 55, (27, 2): 82, (28, 1): 110, (28, 2): 55,
        }
        self.walls = [[1000, 1000, 2500, 1000]]  # restrição FICTÍCIA para visualização
        self.no_go = [[4500, 1000, 6000, 1800]]

    # ------------------------------------------------------------------ raw API
    def info(self) -> dict[str, Any]:
        return {"model": "dreame.vacuum.mc1808", "fw_ver": "4.3.3_1122 (simulado)", "hw_ver": "SIM",
                "mac": "00:00:00:00:00:00", "simulated": True}

    def get_raw_properties(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.tick()
        out = []
        with self._lock:
            for it in items:
                key = (it["siid"], it["piid"])
                if key in self.p:
                    out.append({**it, "code": 0, "value": self.p[key]})
                else:
                    out.append({**it, "code": -4004})
        return out

    def set_raw_property(self, siid: int, piid: int, value: Any) -> dict[str, Any]:
        with self._lock:
            if (siid, piid) not in self.p:
                return {"siid": siid, "piid": piid, "code": -4004}
            self.p[(siid, piid)] = value
        return {"siid": siid, "piid": piid, "code": 0}

    def raw_action(self, siid: int, aiid: int, params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        params = params or []
        args = {p["piid"]: p["value"] for p in params}
        with self._lock:
            ok = {"code": 0, "out": []}
            if (siid, aiid) == (3, 1):
                if self.p[(3, 2)] != 3 or not self.route:
                    self._start_task(self._house_route(), mode=2)
                else:
                    self._set_status(1, 2)
            elif (siid, aiid) in ((3, 2), (18, 2)):
                self._set_status(3 if (siid, aiid) == (18, 2) else 2, 1 if (siid, aiid) == (18, 2) else 2)
                if (siid, aiid) == (3, 2):
                    self.route = []
            elif (siid, aiid) == (2, 1):
                self.route = [(CHARGER[0], CHARGER[1])]
                self._set_status(5, 3)
            elif (siid, aiid) == (18, 1):
                mode = args.get(1)
                if mode == 19:
                    areas = json.loads(args.get(21, "{}")).get("areas", [])
                    route: list[tuple[int, int]] = []
                    for a in areas:
                        route += _lawnmower(*a[:4]) * int(a[4] if len(a) > 4 else 1)
                    self._start_task(route, mode=19)
                elif mode == 18:
                    sel = json.loads(args.get(21, "{}")).get("selects", [])
                    route = []
                    for s in sel:
                        room = next((r for r in ROOMS if r[0] == s[0]), None)
                        if room:
                            route += _lawnmower(*room[2:]) * int(s[1])
                    self._start_task(route, mode=18)
                else:
                    self._start_task(self._house_route(), mode=2)
            elif (siid, aiid) in ((17, 1), (24, 3), (23, 1), (21, 1)):
                pass
            elif (siid, aiid) == (26, 1):
                self.p[(26, 1)], self.p[(26, 2)] = 300, 100
            elif (siid, aiid) == (27, 1):
                self.p[(27, 1)], self.p[(27, 2)] = 100, 150
            elif (siid, aiid) == (28, 1):
                self.p[(28, 1)], self.p[(28, 2)] = 200, 100
            else:
                return {"code": -4004}
            return ok

    # ------------------------------------------------------------------ simulação
    def _house_route(self) -> list[tuple[int, int]]:
        route: list[tuple[int, int]] = []
        for r in ROOMS:
            route += _lawnmower(*r[2:])
        return route

    def _set_status(self, status: int, mode: int) -> None:
        self.p[(3, 2)], self.p[(18, 1)] = status, mode
        self.p[(2, 2)] = 1 if status == 6 else (5 if status == 5 else 2)

    def _start_task(self, route: list[tuple[int, int]], mode: int) -> None:
        self.route = list(route) + [(CHARGER[0], CHARGER[1])]
        self.trail = [[int(self.pose[0]), int(self.pose[1])]]
        self.cleaned_mm2 = 0.0
        self.clean_seconds = 0.0
        self._set_status(1, mode)

    def tick(self) -> None:
        now = time.monotonic()
        dt = (now - self._last_tick) * self.time_scale
        self._last_tick = now
        with self._lock:
            status = self.p[(3, 2)]
            if status in (1, 5) and self.route:
                dist = self.SPEED_MM_S * dt
                while dist > 0 and self.route:
                    tx, ty = self.route[0]
                    dx, dy = tx - self.pose[0], ty - self.pose[1]
                    d = math.hypot(dx, dy)
                    if d <= dist:
                        self.pose[0], self.pose[1] = tx, ty
                        self.route.pop(0)
                        self.trail.append([int(tx), int(ty)])
                        dist -= d
                    else:
                        self.pose[0] += dx / d * dist
                        self.pose[1] += dy / d * dist
                        self.pose[2] = int(math.degrees(math.atan2(dy, dx)))
                        if status == 1:
                            self.cleaned_mm2 += dist * 220
                        dist = 0
                if status == 1:
                    self.clean_seconds += dt
                    self.p[(2, 1)] = max(5, self.p[(2, 1)] - dt / 120)
                self.p[(18, 2)] = int(self.clean_seconds // 60)
                self.p[(18, 3)] = self.p[(18, 4)] = int(self.cleaned_mm2 / 1e6)
                if not self.route:
                    if status == 1:
                        self.p[(18, 14)] += 1
                        self.p[(18, 13)] += self.p[(18, 2)]
                        self.p[(18, 15)] += self.p[(18, 4)]
                    self._set_status(6, 6)
            elif status == 6:
                self.p[(2, 1)] = min(100, self.p[(2, 1)] + dt / 30)
            self.p[(2, 1)] = int(round(self.p[(2, 1)]))

    def map_file(self) -> str:
        """Arquivo de mapa no MESMO formato da Cloud (para exercitar o parser)."""
        self.tick()
        with self._lock:
            tr = ""
            for i, (x, y) in enumerate(self.trail[-4000:]):
                if i == 0:
                    tr, px, py = f"M{x},{y}", x, y
                else:
                    tr += f"L{x - px},{y - py}"
                    px, py = x, y
            extra = {"tr": tr, "vw": {"line": self.walls, "rect": self.no_go, "mop": []},
                     "simulated": True}
            return encode_map(pixels=self._pixels, width=W, height=H, pixel_size=PIXEL, left=LEFT, top=TOP,
                              robot=(int(self.pose[0]), int(self.pose[1]), int(self.pose[2])), charger=CHARGER,
                              extra=extra)

    @staticmethod
    def room_names() -> dict[int, str]:
        return {r[0]: r[1] for r in ROOMS}
