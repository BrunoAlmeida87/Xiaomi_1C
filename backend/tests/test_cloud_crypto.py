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
