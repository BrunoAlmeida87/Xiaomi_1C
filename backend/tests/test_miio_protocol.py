import json
import socket
import threading

import pytest

from xiaomi1c.robot import miio_protocol as mp
from xiaomi1c.robot.transport import DeviceError, MiioTransport

TOKEN_HEX = "00112233445566778899aabbccddeeff"
TOKEN = bytes.fromhex(TOKEN_HEX)


def test_encrypt_matches_python_miio_reference():
    # Vetor gerado com miio.protocol.Utils.encrypt (python-miio 0.5.12)
    ct = mp.encrypt(b'{"id":1,"method":"miIO.info","params":[]}', TOKEN)
    assert ct.hex() == ("a5516ec6151955dc2bb2d43e7c84c18352a39a7f22fd2903d282a5783c6d56ac"
                        "8c9c7629130a25fac17d38175c1a7799")
    assert mp.decrypt(ct, TOKEN) == b'{"id":1,"method":"miIO.info","params":[]}'


def test_packet_roundtrip_and_checksum():
    pkt = mp.build_packet({"id": 7, "method": "get_properties", "params": []}, TOKEN, 0x1234, 99)
    header, payload = mp.parse_packet(pkt, TOKEN)
    assert header.device_id == 0x1234 and header.stamp == 99
    assert payload["id"] == 7
    bad = pkt[:-1] + bytes([pkt[-1] ^ 1])
    with pytest.raises(mp.ProtocolError):
        mp.parse_packet(bad, TOKEN)
    with pytest.raises(mp.ProtocolError):
        mp.parse_packet(pkt, bytes(16))


def test_hello_packet():
    h = mp.parse_header(mp.HELLO_PACKET)
    assert h.is_hello and len(mp.HELLO_PACKET) == 32


@pytest.mark.parametrize("bad", ["", "123", "zz" * 16])
def test_invalid_token(bad):
    with pytest.raises(ValueError):
        mp.parse_token(bad)


class FakeRobot(threading.Thread):
    """Servidor UDP que emula o miIO do robô (handshake + respostas cifradas)."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.received = []

    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
            except OSError:
                return
            header, msg = mp.parse_packet(data, TOKEN)
            if msg is None:
                import struct
                hello = struct.pack(">HHIII", 0x2131, 32, 0, 0xABCD, 1000) + b"\xff" * 16
                self.sock.sendto(hello, addr)
                continue
            self.received.append(msg)
            if msg["method"] == "fail":
                resp = {"id": msg["id"], "error": {"code": -5001, "message": "boom"}}
            else:
                resp = {"id": msg["id"], "result": [{"did": "x", "siid": 2, "piid": 1, "code": 0, "value": 88}]}
            self.sock.sendto(mp.build_packet(resp, TOKEN, 0xABCD, 1001), addr)


def test_transport_end_to_end(monkeypatch):
    fake = FakeRobot()
    fake.start()
    monkeypatch.setattr("xiaomi1c.robot.transport.PORT", fake.port)
    t = MiioTransport("127.0.0.1", TOKEN_HEX, timeout=2, retries=1)
    res = t.send("get_properties", [{"did": "x", "siid": 2, "piid": 1}])
    assert res[0]["value"] == 88
    assert fake.received[0]["params"] == [{"did": "x", "siid": 2, "piid": 1}]
    with pytest.raises(DeviceError):
        t.send("fail")
    fake.sock.close()
