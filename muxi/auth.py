from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Tuple


def generate_hmac_signature(secret_key: str, method: str, path: str) -> Tuple[str, int]:
    timestamp = int(time.time())
    sign_path = path.split("?", 1)[0]
    message = f"{timestamp};{method};{sign_path}".encode()
    mac = hmac.new(secret_key.encode(), message, hashlib.sha256)
    signature = base64.b64encode(mac.digest()).decode()
    return signature, timestamp


def build_auth_header(key_id: str, secret_key: str, method: str, path: str) -> str:
    signature, ts = generate_hmac_signature(secret_key, method, path)
    return f"MUXI-HMAC key={key_id}, timestamp={ts}, signature={signature}"
