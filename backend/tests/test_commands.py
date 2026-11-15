import json

import pytest

from xiaomi1c.robot import spec_1c
from xiaomi1c.robot.commands import CommandExecutor, CommandRejected
from xiaomi1c.robot.simulator import SimulatedRobot


def make(experimental=False):
    audit = []
    return CommandExecutor(SimulatedRobot(time_scale=100), lambda: experimental, audit.append), audit


def test_moving_commands_require_confirmation():
    ex, _ = make()
    with pytest.raises(CommandRejected) as e:
        ex.execute("start")
    assert e.value.reason == "confirmation_required"
    res = ex.execute("start", confirm=True)
    assert res.ok and res.simulated and res.sent == [{"type": "action", "siid": 3, "aiid": 1, "in": []}]


def test_experimental_blocked_by_default():
    ex, _ = make(experimental=False)
    with pytest.raises(CommandRejected) as e:
        ex.execute("clean_zone", {"zones": [[0, 0, 1000, 1000]]}, confirm=True)
    assert e.value.reason == "experimental_disabled"


def test_not_implemented_never_sent():
    ex, audit = make(experimental=True)
    for cid in ("set_virtual_walls", "edit_rooms", "edit_navigation_map"):
        with pytest.raises(CommandRejected) as e:
            ex.execute(cid, confirm=True)
        assert e.value.reason == "not_implemented"
    assert audit == []


def test_zone_payload_exact_format():
    p = spec_1c.zone_payload([[1000, -500, -1000, 500]], repeats=2)
    assert p[0] == {"piid": 1, "value": 19}
    assert json.loads(p[1]["value"]) == {"areas": [[-1000, -500, 1000, 500, 2, 1, 1]]}
    assert " " not in p[1]["value"]
    with pytest.raises(ValueError):
        spec_1c.zone_payload([[0, 0, 100, 100]])


def test_rooms_payload_is_minified_string():
    p = spec_1c.rooms_payload([4, 2], repeats=1, fan_speed=2)
    assert p[1]["value"] == '{"selects":[[4,1,2,3,1],[2,1,2,3,2]]}'


def test_point_emulation_and_validation():
    assert spec_1c.point_to_zone(100, 200, 1000) == [-400, -300, 600, 700]
    ex, _ = make(experimental=True)
    res = ex.execute("clean_point", {"x": 0, "y": 0}, confirm=True)
    assert json.loads(res.sent[0]["in"][1]["value"])["areas"][0][:4] == [-500, -500, 500, 500]
    with pytest.raises(CommandRejected):
        ex.execute("set_fan_speed", {"value": 9})
    with pytest.raises(CommandRejected):
        ex.execute("set_dnd", {"enabled": True, "start": "25:00", "stop": "08:00"}, confirm=True)


def test_audit_records_without_secrets():
    ex, audit = make()
    ex.execute("locate")
    assert audit[0]["command"] == "locate" and audit[0]["simulated"] is True
