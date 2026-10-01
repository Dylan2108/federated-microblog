"""Contraseñas (scrypt) y tokens de sesión firmados con HMAC. Sólo biblioteca estándar."""

import base64
import hashlib
import hmac
import secrets
import time

from app.core.config import settings

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"{salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)

def sign(payload: str) -> str:
    return hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()

def create_token(username: str) -> str:
    """Token `usuario:caducidad:firma` en base64. No necesita guardarse en la BD."""
    payload = f"{username}:{int(time.time()) + settings.token_ttl_seconds}"
    return base64.urlsafe_b64encode(f"{payload}:{sign(payload)}".encode()).decode()

def read_token(token: str) -> str | None:
    """Devuelve el usuario si el token es válido y no ha caducado."""
    try:
        username, expires, signature = base64.urlsafe_b64decode(token).decode().split(":")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, sign(f"{username}:{expires}")):
        return None
    if int(expires) < time.time():
        return None
    return username