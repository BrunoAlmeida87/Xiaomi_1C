import time

from fastapi.testclient import TestClient

from xiaomi1c.api.app import create_app
from xiaomi1c.logsetup import redact
from xiaomi1c.secrets_store import ROBOT_TOKEN


def test_csrf_and_host_protection(core):
    app = create_app(core)
    with TestClient(app) as raw:
        assert raw.post("/api/commands/locate", json={}).status_code == 403
        assert raw.get("/api/health", headers={"host": "evil.example"}).status_code == 403
        assert raw.get("/api/health").status_code == 200


def test_state_never_exposes_token(client, core):
    tok = "ab" * 16
    assert client.put("/api/secrets/token", json={"token": tok}).status_code == 200
    body = client.get("/api/state").text
    assert tok not in body
    assert core.secrets.get(ROBOT_TOKEN) == tok
    assert client.put("/api/secrets/token", json={"token": "123"}).status_code == 400


def test_status_and_commands_flow(client):
    st = client.get("/api/status").json()
    assert st["simulated"] is True and st["status"] == 6
    r = client.post("/api/commands/start", json={})
    assert r.status_code == 403 and r.json()["detail"]["reason"] == "confirmation_required"
    r = client.post("/api/commands/start", json={"confirm": True})
    assert r.status_code == 200 and r.json()["ok"]
    time.sleep(0.3)
    assert client.get("/api/status").json()["status"] in (1, 6)
    r = client.post("/api/commands/clean_rooms", json={"params": {"rooms": [1]}, "confirm": True})
    assert r.json()["detail"]["reason"] == "experimental_disabled"
    client.put("/api/settings", json={"allow_experimental": True})
    r = client.post("/api/commands/clean_rooms", json={"params": {"rooms": [1]}, "confirm": True})
    assert r.status_code == 200
    assert client.get("/api/audit").json()[0]["command"] == "clean_rooms"


def test_capabilities_matrix(client):
    caps = client.get("/api/capabilities").json()
    ids = {c["id"]: c for c in caps["commands"]}
    assert ids["set_virtual_walls"]["evidence"] == "not_implemented"
    assert ids["clean_zone"]["evidence"] == "experimental"
    assert ids["start"]["requires_confirmation"]
    # sem probe do robô real, nada é marcado como comprovado
    assert all(p["evidence"] != "verified" for p in caps["properties"])


def test_map_regions_drafts(client):
    m = client.get("/api/map").json()
    assert m["simulated"] is True and m["source"] == "simulator" and len(m["rooms"]) == 4
    assert client.put("/api/rooms/1/name", json={"name": "Living"}).status_code == 200
    m = client.post("/api/map/refresh").json()
    assert any(r["name"] == "Living" for r in m["rooms"])
    assert client.get("/api/maps").json()
    rid = client.post("/api/regions", json={"name": "Mesa", "kind": "zone", "data": {"zones": [[0, 0, 1000, 1000]]}}).json()["id"]
    assert client.put(f"/api/regions/{rid}", json={"name": "Mesa 2", "kind": "zone", "data": {"zones": []}}).status_code == 200
    assert client.get("/api/regions").json()[0]["name"] == "Mesa 2"
    assert client.delete(f"/api/regions/{rid}").status_code == 200
    d = client.post("/api/drafts", json={"name": "Parede", "kind": "virtual_wall", "data": {"line": [0, 0, 1, 1]}}).json()
    assert d["robot_recognized"] is False
    assert client.get("/api/drafts").json()[0]["robot_recognized"] is False


def test_real_mode_without_config_is_explicit(client):
    client.put("/api/settings", json={"mode": "real"})
    st = client.get("/api/state").json()
    assert st["connection"]["state"] == "not_configured"
    assert client.get("/api/status").status_code == 409


def test_probe_simulated(client):
    res = client.post("/api/probe").json()
    assert res["simulated"] and res["model_confirmed"]
    assert any(r["siid"] == 2 and r["piid"] == 1 for r in res["readable"])


def test_redaction():
    assert "00112233445566778899aabbccddeeff" not in redact("token=00112233445566778899aabbccddeeff")
    assert "abc123" not in redact('{"serviceToken": "abc123"}')
