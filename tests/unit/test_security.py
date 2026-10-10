import base64

from app.core import security
from app.core.config import settings

def test_password_roundtrip():
    stored = security.hash_password("secreto1")
    assert security.verify_password("secreto1", stored)
    assert not security.verify_password("otra", stored)

def test_same_password_different_hash():
    assert security.hash_password("secreto1") != security.hash_password("secreto1")

def test_token_roundtrip():
    assert security.read_token(security.create_token("ana")) == "ana"

def test_tampered_token_rejected():
    user, expires, signature = base64.urlsafe_b64decode(security.create_token("ana")).decode().split(":")
    forged = base64.urlsafe_b64encode(f"admin:{expires}:{signature}".encode()).decode()
    assert security.read_token(forged) is None

def test_garbage_token_rejected():
    assert security.read_token("basura") is None

def test_expired_token_rejected(monkeypatch):
    monkeypatch.setattr(settings, "token_ttl_seconds", -1)
    assert security.read_token(security.create_token("ana")) is None