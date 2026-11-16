import base64
import os

import pytest

from xiaomi1c.cloud import crypto


def test_rc4_matches_cryptography_arc4():
    try:
        from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4
    except ImportError:
        pytest.skip("ARC4 indisponível nesta versão do cryptography")
    from cryptography.hazmat.primitives.ciphers import Cipher

    key, data = os.urandom(32), b"payload de teste" * 5
    enc = Cipher(ARC4(key), mode=None).encryptor()
    enc.update(bytes(1024))  # descarte de 1024 bytes, como no protocolo
    assert crypto.rc4(key, data) == enc.update(data)


def test_rc4_roundtrip():
    snonce = base64.b64encode(os.urandom(32)).decode()
    ct = crypto.encrypt_rc4(snonce, '{"a":1}')
    assert crypto.decrypt_rc4(snonce, ct) == b'{"a":1}'


def test_encrypted_params_shape():
    ssec = base64.b64encode(os.urandom(16)).decode()
    nonce = crypto.generate_nonce(1_700_000_000_000)
    sn = crypto.signed_nonce(ssec, nonce)
    out = crypto.build_encrypted_params("https://de.api.io.mi.com/app/home/device_list", "POST", sn, nonce, {"data": "{}"}, ssec)
    assert set(out) == {"data", "rc4_hash__", "signature", "ssecurity", "_nonce"}
    assert crypto.decrypt_rc4(sn, out["data"]) == b"{}"


def test_list_devices_falls_back_to_homes():
    from xiaomi1c.cloud.client import CloudSession, XiaomiCloud

    cloud = XiaomiCloud(CloudSession("1", "c3M=", "tok"))
    responses = {
        "/home/device_list": {"result": {"list": [{"did": "9", "model": "yeelink.light", "token": "t9"}]}},
        "/v2/homeroom/gethome": {"result": {"homelist": [{"id": "77", "uid": 123}], "share_home_list": []}},
        "/v2/home/home_device_list": {"result": {"device_info": [
            {"did": "42", "name": "Robô", "model": "dreame.vacuum.mc1808", "token": "abc", "localip": "192.168.0.9"}]}},
    }
    cloud.call = lambda server, path, data: responses[path]
    devs = {d["did"]: d for d in cloud.list_devices("us")}
    assert set(devs) == {"9", "42"}
    assert devs["42"]["uid"] == 123 and devs["42"]["localip"] == "192.168.0.9" and devs["42"]["server"] == "us"
