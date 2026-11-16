from xiaomi1c.robot.simulator import SimulatedRobot
from xiaomi1c.robot.status import probe
from xiaomi1c.robot.transport import CommunicationError, DeviceError


class OddRobot(SimulatedRobot):
    """Robô que imita respostas fora do padrão."""

    def get_raw_properties(self, items, quick=False):
        siid = items[0]["siid"]
        if siid == 5:
            raise CommunicationError("silêncio")
        if siid == 18 and len(items) > 1:
            raise DeviceError({"code": -5001, "message": "lote recusado"})
        if siid == 7:
            return {"code": -1}  # não é lista
        if siid == 9:
            return ["lixo"]
        return super().get_raw_properties(items)

    def info(self):
        return "texto"  # miIO.info estranho


def test_probe_survives_odd_responses():
    res = probe(OddRobot(), max_siid=20, delay=0)
    assert 5 in res["silent_siids"]
    assert any((r["siid"], r["piid"]) == (18, 6) for r in res["readable"])  # recuperado item a item
    assert res["anomalies"]
    assert res["model_confirmed"] is False


def test_unexpected_error_returns_json(core, client, monkeypatch):
    def boom():
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(core, "run_probe", boom)
    r = client.post("/api/probe")
    assert r.status_code == 500
    assert "RuntimeError" in r.json()["detail"]
