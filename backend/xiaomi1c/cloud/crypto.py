"""Primitivas da API criptografada da Xiaomi Cloud (RC4 + assinaturas).

Reimplementação do esquema usado pelo Xiaomi-cloud-tokens-extractor e pelo
Xiaomi Cloud Map Extractor (``execute_api_call_encrypted``). RC4 é implementado
aqui em Python puro para evitar dependência de PyCryptodome; ele é exigido pelo
protocolo da Xiaomi — não é usado para proteger nada localmente.
"""
from __future__ import annotations

import base64
import hashlib
import os
import time


def rc4(key: bytes, data: bytes, drop: int = 1024) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for n in range(drop + len(data)):
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        if n >= drop:
            out.append(data[n - drop] ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def encrypt_rc4(signed_nonce_b64: str, payload: str) -> str:
    return base64.b64encode(rc4(base64.b64decode(signed_nonce_b64), payload.encode())).decode()


def decrypt_rc4(signed_nonce_b64: str, payload_b64: str) -> bytes:
    return rc4(base64.b64decode(signed_nonce_b64), base64.b64decode(payload_b64))


def generate_nonce(millis: int | None = None) -> str:
    millis = int(time.time() * 1000) if millis is None else millis
    return base64.b64encode(os.urandom(8) + int(millis / 60000).to_bytes(4, "big")).decode()


def signed_nonce(ssecurity_b64: str, nonce_b64: str) -> str:
    digest = hashlib.sha256(base64.b64decode(ssecurity_b64) + base64.b64decode(nonce_b64)).digest()
    return base64.b64encode(digest).decode()


def enc_signature(url: str, method: str, signed_nonce_b64: str, params: dict[str, str]) -> str:
    parts = [method.upper(), url.split("com", 1)[1].replace("/app/", "/")]
    parts += [f"{k}={v}" for k, v in params.items()]
    parts.append(signed_nonce_b64)
    return base64.b64encode(hashlib.sha1("&".join(parts).encode()).digest()).decode()  # noqa: S324


def build_encrypted_params(url: str, method: str, snonce: str, nonce: str, params: dict[str, str], ssecurity: str) -> dict[str, str]:
    params = dict(params)
    params["rc4_hash__"] = enc_signature(url, method, snonce, params)
    for k, v in list(params.items()):
        params[k] = encrypt_rc4(snonce, v)
    params["signature"] = enc_signature(url, method, snonce, params)
    params["ssecurity"] = ssecurity
    params["_nonce"] = nonce
    return params
