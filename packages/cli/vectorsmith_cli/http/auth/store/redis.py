"""Redis-backed token store so two ``serve`` replicas share builtin OAuth tokens."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from argon2 import PasswordHasher

_PH = PasswordHasher()
_PREFIX = "vectorsmith:auth:"


class RedisAuthStore:
    """Duck-types ``builtin_oauth.store.AuthStore`` on a Redis client."""

    def __init__(self, url: str | None = None, *, client: Any = None) -> None:
        if client is not None:
            self._r = client
        else:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError(
                    "redis extra not installed: pip install 'vectorsmith[auth-redis]'"
                ) from exc
            if not url:
                raise RuntimeError("--redis-url is required for --auth-store redis")
            self._r = redis.Redis.from_url(url, decode_responses=True)

    def _key(self, *parts: str) -> str:
        return _PREFIX + ":".join(parts)

    def _hash(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def access_secret_hash(self) -> str | None:
        val = self._r.get(self._key("meta", "secret_hash"))
        return str(val) if val else None

    def bootstrap_secret(self) -> str | None:
        if self.access_secret_hash():
            return None
        return self.rotate_secret()

    def verify_secret(self, secret: str) -> bool:
        digest = self.access_secret_hash()
        if not digest:
            return False
        try:
            _PH.verify(digest, secret)
            return True
        except Exception:
            return False

    def rotate_secret(self) -> str:
        secret = secrets.token_urlsafe(24)
        self._r.set(self._key("meta", "secret_hash"), _PH.hash(secret))
        self.revoke_all()
        return secret

    def write_secret_once(self, secret: str) -> Any:
        import os
        from pathlib import Path

        dest = Path.home() / ".vectorsmith" / "access-secret.once"
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secret)
            fh.write("\n")
        return dest

    def revoke_all(self) -> None:
        for pattern in (self._key("token", "*"), self._key("code", "*")):
            keys = list(self._r.keys(pattern) or [])
            if keys:
                self._r.delete(*keys)

    def register_client(self, redirect_uri: str) -> str:
        client_id = secrets.token_urlsafe(16)
        self._r.set(self._key("client", client_id), redirect_uri)
        return client_id

    def issue_code(self, client_id: str, redirect_uri: str, challenge: str) -> str:
        code = secrets.token_urlsafe(24)
        self._r.set(
            self._key("code", code),
            json.dumps(
                {
                    "client_id": client_id,
                    "redirect_uri": redirect_uri,
                    "challenge": challenge,
                }
            ),
            ex=300,
        )
        return code

    def consume_code(self, code: str, verifier: str, redirect_uri: str) -> bool:
        import base64
        import hashlib as hl

        raw = self._r.get(self._key("code", code))
        if not raw:
            return False
        self._r.delete(self._key("code", code))
        row = json.loads(str(raw))
        if row.get("redirect_uri") != redirect_uri:
            return False
        digest = base64.urlsafe_b64encode(hl.sha256(verifier.encode()).digest()).rstrip(b"=")
        return digest.decode() == row.get("challenge")

    def issue_tokens(self) -> dict[str, str]:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        now = time.time()
        self._r.set(
            self._key("token", self._hash(access)),
            json.dumps({"kind": "access", "expires_at": now + 15 * 60}),
            ex=15 * 60,
        )
        self._r.set(
            self._key("token", self._hash(refresh)),
            json.dumps({"kind": "refresh", "expires_at": now + 30 * 24 * 3600}),
            ex=30 * 24 * 3600,
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": "900",
        }

    def rotate_refresh(self, refresh: str) -> dict[str, str] | None:
        key = self._key("token", self._hash(refresh))
        raw = self._r.get(key)
        if not raw:
            return None
        row = json.loads(str(raw))
        if row.get("kind") != "refresh" or float(row.get("expires_at") or 0) < time.time():
            return None
        self._r.delete(key)
        return self.issue_tokens()

    def valid_access(self, token: str) -> bool:
        raw = self._r.get(self._key("token", self._hash(token)))
        if not raw:
            return False
        row = json.loads(str(raw))
        return row.get("kind") == "access" and float(row.get("expires_at") or 0) >= time.time()
