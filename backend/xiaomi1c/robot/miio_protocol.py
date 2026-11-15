"""Codificação/decodificação de pacotes do protocolo local miIO (UDP 54321).

Implementação própria, baseada na documentação e no código do python-miio
(https://github.com/rytilahti/python-miio, ``miio/protocol.py``). Mantemos uma
versão própria e mínima para:

* não depender de ``netifaces`` (dependência transitiva do python-miio que
  frequentemente não possui wheel para Windows em Python recente);
* ter controle total de logs (o token nunca é registrado);
* permitir testes determinísticos.

Formato do pacote (big-endian)::

    0      2      4          8          12         16                32
    +------+------+----------+----------+----------+-----------------+
    |2131  |len   |unknown   |device id |stamp     |checksum (md5)   |  + payload cifrado
    +------+------+----------+----------+----------+-----------------+

* ``checksum = md5(header[0:16] + token + payload_cifrado)``
* criptografia: AES-128-CBC, PKCS#7, ``key = md5(token)``, ``iv = md5(key + token)``
* pacote "hello" (handshake): 32 bytes, ``unknown``/``device id``/``stamp``/``checksum`` = 0xFF.
"""
from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = 0x2131
HEADER_LEN = 32
HELLO_PACKET = bytes.fromhex("21310020" + "ff" * 28)


class ProtocolError(Exception):
    """Pacote malformado, checksum inválido ou falha de decodificação."""


def _md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()  # noqa: S324 - exigido pelo protocolo


def parse_token(token_hex: str) -> bytes:
    """Converte o token (32 caracteres hexadecimais) em bytes, validando-o."""
    token_hex = (token_hex or "").strip()
    if len(token_hex) != 32:
        raise ValueError("O token deve ter exatamente 32 caracteres hexadecimais")
    try:
        return bytes.fromhex(token_hex)
    except ValueError as exc:
        raise ValueError("O token contém caracteres não hexadecimais") from exc


def key_iv(token: bytes) -> tuple[bytes, bytes]:
    key = _md5(token)
    iv = _md5(key + token)
    return key, iv


def encrypt(plaintext: bytes, token: bytes) -> bytes:
    key, iv = key_iv(token)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(padded) + enc.finalize()


def decrypt(ciphertext: bytes, token: bytes) -> bytes:
    key, iv = key_iv(token)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as exc:  # padding inválido => token errado na prática
        raise ProtocolError("Falha ao decifrar a resposta (token incorreto?)") from exc


@dataclass(frozen=True)
class Header:
    length: int
    unknown: int
    device_id: int
    stamp: int
    checksum: bytes

    @property
    def is_hello(self) -> bool:
        return self.length == HEADER_LEN


def parse_header(packet: bytes) -> Header:
    if len(packet) < HEADER_LEN:
        raise ProtocolError(f"Pacote curto demais ({len(packet)} bytes)")
    magic, length, unknown, did, stamp = struct.unpack(">HHIII", packet[:16])
    if magic != MAGIC:
        raise ProtocolError(f"Magic inválido: 0x{magic:04x}")
    if length != len(packet):
        raise ProtocolError(f"Tamanho declarado {length} difere do recebido {len(packet)}")
    return Header(length, unknown, did, stamp, packet[16:32])


def build_packet(payload: dict[str, Any], token: bytes, device_id: int, stamp: int) -> bytes:
    """Monta um pacote cifrado com o payload JSON."""
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encrypted = encrypt(data, token)
    length = HEADER_LEN + len(encrypted)
    head = struct.pack(">HHIII", MAGIC, length, 0, device_id, stamp)
    checksum = _md5(head + token + encrypted)
    return head + checksum + encrypted


def parse_packet(packet: bytes, token: bytes) -> tuple[Header, dict[str, Any] | None]:
    """Valida checksum, decifra e devolve (cabeçalho, JSON). Hello devolve JSON None."""
    header = parse_header(packet)
    if header.is_hello:
        return header, None
    encrypted = packet[HEADER_LEN:]
    expected = _md5(packet[:16] + token + encrypted)
    if expected != header.checksum:
        raise ProtocolError("Checksum inválido (token incorreto ou pacote corrompido)")
    raw = decrypt(encrypted, token)
    # Alguns firmwares terminam o JSON com bytes nulos; outros produzem
    # vírgulas finais ou caracteres inválidos. Tratamos os casos conhecidos.
    text = raw.rstrip(b"\x00").decode("utf-8", errors="replace")
    try:
        return header, json.loads(text)
    except json.JSONDecodeError:
        cleaned = text.replace(",,", ",").replace("[,", "[").replace(",]", "]").replace(",}", "}")
        try:
            return header, json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"Resposta não é JSON válido: {text[:120]!r}") from exc
