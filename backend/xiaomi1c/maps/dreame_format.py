"""Decodificador (e codificador para testes/simulação) do formato de mapa Dreame.

Formato documentado a partir do Xiaomi Cloud Map Extractor
(``custom_components/xiaomi_cloud_map_extractor/dreame/map_data_parser.py`` e
``image_handler.py``), que lista o ``dreame.vacuum.mc1808`` como suportado.

Arquivo baixado da Cloud
------------------------
Texto base64 *URL-safe* (``-``→``+``, ``_``→``/``) de um bloco **zlib**.

Bloco descompactado
-------------------
* 27 bytes de cabeçalho (int16 little-endian, exceto ``frame_type``)::

      0  map_index      2  frame_id      4  frame_type (int8: 'I'=73, 'P'=80)
      5  robô x         7  robô y        9  robô ângulo
      11 base x         13 base y        15 base ângulo
      17 pixel_size(mm) 19 largura(px)   21 altura(px)
      23 left (mm)      25 top (mm)

* ``largura * altura`` bytes de pixels (linha 0 = menor Y).
* JSON UTF-8 com dados adicionais: ``tr`` (trajetória), ``vw`` (restrições:
  ``line`` paredes virtuais, ``rect`` zonas proibidas, ``mop`` zonas sem pano),
  ``sa`` (segmentos ativos), ``seg_inf`` (nomes de cômodos em base64), ``rism``
  (mapa salvo aninhado, mesmo formato, quando ``ris == 2``) e outros.

Pixels
------
* mapa "regular": ``seg = px >> 2`` (cômodo se 0 < seg < 62), senão ``px & 3``:
  0 = fora, 1 = chão, 2 = parede.
* mapa "rism": ``parede = px >> 7``, ``seg = px & 0x7F``.

Sistema de coordenadas (milímetros, mesmo referencial dos comandos)
-------------------------------------------------------------------
``x_mm = left + coluna * pixel_size`` e ``y_mm = top + linha * pixel_size``,
Y crescente "para cima" (a renderização inverte as linhas).
"""
from __future__ import annotations

import base64
import json
import re
import struct
import zlib
from dataclasses import asdict, dataclass, field
from typing import Any

HEADER_SIZE = 27
FRAME_I = 73
FRAME_P = 80

CLASS_NONE, CLASS_FLOOR, CLASS_WALL = 0, 1, 2
_PATH_RE = re.compile(r"(?P<op>[SLM])(?P<x>-?\d+),(?P<y>-?\d+)")


class MapFormatError(Exception):
    pass


@dataclass
class Pose:
    x: int
    y: int
    angle: int = 0


@dataclass
class Room:
    id: int
    name: str
    bbox: list[int]  # [x0, y0, x1, y1] em mm


@dataclass
class MapModel:
    source: str
    map_index: int
    frame_type: str
    pixel_size: int
    width: int
    height: int
    left: int
    top: int
    robot: Pose | None
    charger: Pose | None
    classes_b64: str  # width*height bytes: 0 fora, 1 chão, 2 parede
    segments_b64: str  # width*height bytes: id do cômodo (0 = nenhum)
    rooms: list[Room] = field(default_factory=list)
    path: list[list[list[int]]] = field(default_factory=list)
    virtual_walls: list[list[int]] = field(default_factory=list)
    no_go_areas: list[list[int]] = field(default_factory=list)
    no_mop_areas: list[list[int]] = field(default_factory=list)
    active_segments: list[int] = field(default_factory=list)
    has_saved_map: bool = False
    extra_keys: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    # utilidades de coordenadas ------------------------------------------------
    def cell_to_mm(self, col: float, row: float) -> tuple[float, float]:
        return self.left + col * self.pixel_size, self.top + row * self.pixel_size

    def mm_to_cell(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.left) / self.pixel_size, (y - self.top) / self.pixel_size


# ----------------------------------------------------------------------------- decode
def unwrap_cloud_file(raw: bytes | str) -> bytes:
    """Converte o arquivo da Cloud (base64 URL-safe + zlib) em bytes do mapa."""
    text = raw.decode("ascii", errors="strict") if isinstance(raw, (bytes, bytearray)) else raw
    text = text.strip().replace("_", "/").replace("-", "+")
    text += "=" * (-len(text) % 4)
    try:
        return zlib.decompress(base64.b64decode(text))
    except (ValueError, zlib.error) as exc:
        raise MapFormatError(f"Arquivo de mapa inválido: {exc}") from exc


def _header(raw: bytes) -> dict[str, int]:
    if len(raw) < HEADER_SIZE:
        raise MapFormatError("Cabeçalho do mapa incompleto")
    (map_index, frame_id) = struct.unpack_from("<hh", raw, 0)
    frame_type = struct.unpack_from("<b", raw, 4)[0]
    vals = struct.unpack_from("<11h", raw, 5)
    keys = ("rx", "ry", "ra", "cx", "cy", "ca", "pixel_size", "width", "height", "left", "top")
    h = dict(zip(keys, vals))
    h.update(map_index=map_index, frame_id=frame_id, frame_type=frame_type)
    return h


def _parse_path(tr: str) -> list[list[list[int]]]:
    paths: list[list[list[int]]] = []
    cur: list[list[int]] | None = None
    x = y = 0
    for m in _PATH_RE.finditer(tr):
        op, dx, dy = m.group("op"), int(m.group("x")), int(m.group("y"))
        if op in ("S", "M") or cur is None:
            cur = []
            paths.append(cur)
            x, y = (dx, dy) if op in ("S", "M") else (x + dx, y + dy)
        else:
            x, y = x + dx, y + dy
        cur.append([x, y])
    return paths


def _rects(items: Any) -> list[list[int]]:
    out = []
    for a in items or []:
        if isinstance(a, (list, tuple)) and len(a) >= 4:
            x0, x1 = sorted((int(a[0]), int(a[2])))
            y0, y1 = sorted((int(a[1]), int(a[3])))
            out.append([x0, y0, x1, y1])
    return out


def _lines(items: Any) -> list[list[int]]:
    return [[int(v) for v in a[:4]] for a in items or [] if isinstance(a, (list, tuple)) and len(a) >= 4]


def parse_map_bytes(raw: bytes, source: str = "cloud", kind: str = "regular") -> MapModel:
    h = _header(raw)
    if h["frame_type"] != FRAME_I:
        raise MapFormatError("Somente quadros completos (I-frame) são suportados")
    w, hgt, ps = h["width"], h["height"], h["pixel_size"]
    if ps <= 0:
        raise MapFormatError("pixel_size inválido")
    n = w * hgt
    if len(raw) < HEADER_SIZE + n:
        raise MapFormatError("Dados de pixels incompletos")
    pixels = raw[HEADER_SIZE : HEADER_SIZE + n]
    tail = raw[HEADER_SIZE + n :]
    extra: dict[str, Any] = {}
    if tail.strip():
        try:
            extra = json.loads(tail.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MapFormatError(f"JSON adicional inválido: {exc}") from exc

    classes = bytearray(n)
    segments = bytearray(n)
    bbox: dict[int, list[int]] = {}
    for i, px in enumerate(pixels):
        if kind == "rism":
            seg = px & 0x7F
            if px >> 7:
                classes[i] = CLASS_WALL
                continue
            if not seg:
                continue
            classes[i] = CLASS_FLOOR
            segments[i] = seg
        else:
            seg = px >> 2
            if 0 < seg < 62:
                classes[i] = CLASS_FLOOR
                segments[i] = seg
            else:
                classes[i] = px & 0b11 if (px & 0b11) in (0, 1, 2) else CLASS_NONE
                continue
        col, row = i % w, i // w
        b = bbox.setdefault(seg, [col, row, col, row])
        b[0], b[1], b[2], b[3] = min(b[0], col), min(b[1], row), max(b[2], col), max(b[3], row)

    names: dict[int, str] = {}
    for k, v in (extra.get("seg_inf") or {}).items():
        try:
            if isinstance(v, dict) and v.get("name"):
                names[int(k)] = base64.b64decode(v["name"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            pass

    left, top = h["left"], h["top"]
    rooms = [
        Room(sid, names.get(sid, f"Cômodo {sid}"),
             [left + b[0] * ps, top + b[1] * ps, left + (b[2] + 1) * ps, top + (b[3] + 1) * ps])
        for sid, b in sorted(bbox.items())
    ]

    model = MapModel(
        source=source,
        map_index=h["map_index"],
        frame_type="I",
        pixel_size=ps,
        width=w,
        height=hgt,
        left=left,
        top=top,
        robot=Pose(h["rx"], h["ry"], h["ra"]),
        charger=Pose(h["cx"], h["cy"], h["ca"]),
        classes_b64=base64.b64encode(bytes(classes)).decode(),
        segments_b64=base64.b64encode(bytes(segments)).decode(),
        rooms=rooms,
        extra_keys=sorted(extra.keys()),
    )
    vw = extra.get("vw") or {}
    if isinstance(vw, dict):
        model.virtual_walls = _lines(vw.get("line"))
        model.no_go_areas = _rects(vw.get("rect"))
        model.no_mop_areas = _rects(vw.get("mop"))
    if isinstance(extra.get("tr"), str):
        model.path = _parse_path(extra["tr"])
    if isinstance(extra.get("sa"), list):
        model.active_segments = [int(s[0]) for s in extra["sa"] if isinstance(s, (list, tuple)) and s]

    # Mapa salvo aninhado (cômodos/restrições definitivos)
    if extra.get("rism") and extra.get("ris") == 2 and kind == "regular":
        saved = parse_map_bytes(unwrap_cloud_file(extra["rism"]), source=source, kind="rism")
        model.has_saved_map = True
        model.rooms = saved.rooms or model.rooms
        model.virtual_walls = saved.virtual_walls or model.virtual_walls
        model.no_go_areas = saved.no_go_areas or model.no_go_areas
        model.no_mop_areas = saved.no_mop_areas or model.no_mop_areas
        if saved.width and saved.height:
            for attr in ("width", "height", "left", "top", "pixel_size", "classes_b64", "segments_b64"):
                setattr(model, attr, getattr(saved, attr))

    # Guarda chaves pequenas para pesquisa (sem trajetória e mapa aninhado)
    model.extra = {k: v for k, v in extra.items() if k not in ("tr", "rism") and len(json.dumps(v)) < 2000}
    return model


def parse_cloud_file(raw: bytes | str, source: str = "cloud") -> MapModel:
    return parse_map_bytes(unwrap_cloud_file(raw), source=source)


# ----------------------------------------------------------------------------- encode
def encode_map(
    *,
    pixels: bytes,
    width: int,
    height: int,
    pixel_size: int = 50,
    left: int = 0,
    top: int = 0,
    robot: tuple[int, int, int] = (0, 0, 0),
    charger: tuple[int, int, int] = (0, 0, 0),
    extra: dict[str, Any] | None = None,
    map_index: int = 1,
) -> str:
    """Gera um arquivo no formato da Cloud. Usado pelo simulador e pelos testes."""
    if len(pixels) != width * height:
        raise ValueError("pixels deve ter width*height bytes")
    head = struct.pack("<hhb", map_index, 1, FRAME_I) + struct.pack(
        "<11h", *robot, *charger, pixel_size, width, height, left, top
    )
    body = head + bytes(pixels) + json.dumps(extra or {}, separators=(",", ":")).encode()
    return base64.b64encode(zlib.compress(body)).decode().replace("/", "_").replace("+", "-")
