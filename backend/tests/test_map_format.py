import base64

import pytest

from xiaomi1c.maps.dreame_format import MapFormatError, encode_map, parse_cloud_file, unwrap_cloud_file
from xiaomi1c.robot.simulator import SimulatedRobot


def _grid():
    w, h = 10, 8
    px = bytearray(w * h)
    for r in range(h):
        for c in range(w):
            if r in (0, h - 1) or c in (0, w - 1):
                px[r * w + c] = 2
            elif c < 5:
                px[r * w + c] = 3 << 2  # cômodo 3
            else:
                px[r * w + c] = 1
    return bytes(px), w, h


def test_parse_header_pixels_and_extras():
    px, w, h = _grid()
    name = base64.b64encode("Sala".encode()).decode()
    raw = encode_map(pixels=px, width=w, height=h, pixel_size=50, left=-200, top=100, robot=(10, 20, 90),
                     charger=(-100, 150, 0),
                     extra={"tr": "M0,0L100,0L0,100", "vw": {"line": [[0, 0, 500, 0]], "rect": [[300, 400, 100, 200]]},
                            "seg_inf": {"3": {"name": name}}, "sa": [[3, 1]]})
    m = parse_cloud_file(raw)
    assert (m.width, m.height, m.pixel_size, m.left, m.top) == (10, 8, 50, -200, 100)
    assert (m.robot.x, m.robot.y, m.robot.angle) == (10, 20, 90)
    assert m.charger.x == -100
    classes = base64.b64decode(m.classes_b64)
    assert classes[0] == 2 and classes[1 * w + 6] == 1
    assert m.rooms[0].id == 3 and m.rooms[0].name == "Sala"
    # bbox do cômodo: colunas 1..4, linhas 1..6
    assert m.rooms[0].bbox == [-200 + 50, 100 + 50, -200 + 5 * 50, 100 + 7 * 50]
    assert m.path == [[[0, 0], [100, 0], [100, 100]]]
    assert m.virtual_walls == [[0, 0, 500, 0]]
    assert m.no_go_areas == [[100, 200, 300, 400]]
    assert m.active_segments == [3]
    assert m.cell_to_mm(2, 3) == (-100, 250)
    assert m.mm_to_cell(-100, 250) == (2, 3)


def test_nested_saved_map_rism():
    w, h = 4, 4
    rism_px = bytes([0x80, 0x80, 0x80, 0x80, 0x80, 5, 5, 0x80, 0x80, 6, 6, 0x80, 0x80, 0x80, 0x80, 0x80])
    rism = encode_map(pixels=rism_px, width=w, height=h, extra={"vw": {"rect": [[0, 0, 100, 100]]}})
    raw = encode_map(pixels=bytes([1] * 16), width=w, height=h, extra={"ris": 2, "rism": rism})
    m = parse_cloud_file(raw)
    assert m.has_saved_map
    assert [r.id for r in m.rooms] == [5, 6]
    assert m.no_go_areas == [[0, 0, 100, 100]]


def test_invalid_files():
    with pytest.raises(MapFormatError):
        unwrap_cloud_file("não é base64!!")
    with pytest.raises(MapFormatError):
        parse_cloud_file(encode_map(pixels=b"", width=0, height=0, pixel_size=0))


def test_simulator_map_is_parseable():
    m = parse_cloud_file(SimulatedRobot().map_file(), source="simulator")
    assert len(m.rooms) == 4 and m.virtual_walls and m.no_go_areas
    assert m.extra.get("simulated") is True
