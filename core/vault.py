import base64
import hashlib
import hmac
import json
import os
import sys

VERSION = 1
ITERATIONS = 150_000
STATE = {"secret": "", "data": None}


def tokens_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "tokens.json")


def keys(secret, salt):
    material = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, ITERATIONS, dklen=64)
    return material[:32], material[32:]


def stream(key, nonce, length):
    blocks = []
    size = 0
    counter = 0
    while size < length:
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        blocks.append(block)
        size += len(block)
        counter += 1
    return b"".join(blocks)[:length]


def xor(data, mask):
    return bytes(a ^ b for a, b in zip(data, mask))


def pack(raw):
    return base64.b64encode(raw).decode("ascii")


def seal(data, secret):
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = keys(secret, salt)
    plain = json.dumps(data, ensure_ascii=False).encode("utf-8")
    cipher = xor(plain, stream(enc_key, nonce, len(plain)))
    mac = hmac.new(mac_key, bytes([VERSION]) + salt + nonce + cipher, hashlib.sha256).digest()
    return json.dumps({
        "v": VERSION,
        "salt": pack(salt),
        "nonce": pack(nonce),
        "data": pack(cipher),
        "mac": pack(mac),
    })


def unseal(text, secret):
    try:
        box = json.loads(text)
        salt = base64.b64decode(box["salt"])
        nonce = base64.b64decode(box["nonce"])
        cipher = base64.b64decode(box["data"])
        mac = base64.b64decode(box["mac"])
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid tokens file") from exc
    enc_key, mac_key = keys(secret, salt)
    expected = hmac.new(mac_key, bytes([VERSION]) + salt + nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise ValueError("Invalid tokens file")
    data = json.loads(xor(cipher, stream(enc_key, nonce, len(cipher))).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid tokens file")
    return data


def write(data, secret, path=None):
    path = path or tokens_path()
    with open(path, "w", encoding="utf-8") as file:
        file.write(seal(data, secret))
    return path


def configure(secret):
    STATE["secret"] = secret
    STATE["data"] = None


def load():
    try:
        with open(tokens_path(), "r", encoding="utf-8") as file:
            return unseal(file.read(), STATE["secret"])
    except (OSError, ValueError):
        return {}


def get(name):
    if STATE["data"] is None:
        STATE["data"] = load()
    return str(STATE["data"].get(name) or "").strip()
