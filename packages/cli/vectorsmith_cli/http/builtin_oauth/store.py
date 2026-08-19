"""Hashed token store (SQLite 0600)."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from pathlib import Path

from argon2 import PasswordHasher

_PH = PasswordHasher()


def default_db_path() -> Path:
    root = Path.home() / ".vectorsmith"
    root.mkdir(parents=True, exist_ok=True)
    return root / "authstate.db"


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS clients (
                client_id TEXT PRIMARY KEY, redirect_uri TEXT, created_at REAL
            );
            CREATE TABLE IF NOT EXISTS codes (
                code TEXT PRIMARY KEY, client_id TEXT, redirect_uri TEXT,
                challenge TEXT, expires_at REAL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token_hash TEXT PRIMARY KEY, kind TEXT, expires_at REAL
            );
            """
        )
        conn.commit()
        conn.close()
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def access_secret_hash(self) -> str | None:
        conn = self._connect()
        row = conn.execute("SELECT v FROM meta WHERE k='secret_hash'").fetchone()
        conn.close()
        return str(row["v"]) if row else None

    def bootstrap_secret(self) -> str | None:
        """Create a one-time access secret if missing. Returns plaintext once."""
        if self.access_secret_hash():
            return None
        secret = secrets.token_urlsafe(24)
        conn = self._connect()
        conn.execute(
            "INSERT INTO meta(k,v) VALUES('secret_hash', ?)",
            (_PH.hash(secret),),
        )
        conn.commit()
        conn.close()
        return secret

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
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO meta(k,v) VALUES('secret_hash', ?)",
            (_PH.hash(secret),),
        )
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM codes")
        conn.commit()
        conn.close()
        return secret

    def revoke_all(self) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM codes")
        conn.commit()
        conn.close()

    def register_client(self, redirect_uri: str) -> str:
        client_id = secrets.token_urlsafe(16)
        conn = self._connect()
        conn.execute(
            "INSERT INTO clients(client_id, redirect_uri, created_at) VALUES(?,?,?)",
            (client_id, redirect_uri, time.time()),
        )
        conn.commit()
        conn.close()
        return client_id

    def issue_code(self, client_id: str, redirect_uri: str, challenge: str) -> str:
        code = secrets.token_urlsafe(24)
        conn = self._connect()
        conn.execute(
            "INSERT INTO codes(code, client_id, redirect_uri, challenge, expires_at) "
            "VALUES(?,?,?,?,?)",
            (code, client_id, redirect_uri, challenge, time.time() + 300),
        )
        conn.commit()
        conn.close()
        return code

    def consume_code(self, code: str, verifier: str, redirect_uri: str) -> bool:
        import base64
        import hashlib as hl

        conn = self._connect()
        row = conn.execute("SELECT * FROM codes WHERE code=?", (code,)).fetchone()
        if row is None or row["expires_at"] < time.time():
            conn.close()
            return False
        if row["redirect_uri"] != redirect_uri:
            conn.close()
            return False
        digest = base64.urlsafe_b64encode(hl.sha256(verifier.encode()).digest()).rstrip(b"=")
        if digest.decode() != row["challenge"]:
            conn.close()
            return False
        conn.execute("DELETE FROM codes WHERE code=?", (code,))
        conn.commit()
        conn.close()
        return True

    def issue_tokens(self) -> dict[str, str]:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        now = time.time()
        conn = self._connect()
        conn.execute(
            "INSERT INTO tokens(token_hash, kind, expires_at) VALUES(?,?,?)",
            (self._hash(access), "access", now + 15 * 60),
        )
        conn.execute(
            "INSERT INTO tokens(token_hash, kind, expires_at) VALUES(?,?,?)",
            (self._hash(refresh), "refresh", now + 30 * 24 * 3600),
        )
        conn.commit()
        conn.close()
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": "900",
        }

    def rotate_refresh(self, refresh: str) -> dict[str, str] | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM tokens WHERE token_hash=? AND kind='refresh'",
            (self._hash(refresh),),
        ).fetchone()
        if row is None or row["expires_at"] < time.time():
            conn.close()
            return None
        conn.execute("DELETE FROM tokens WHERE token_hash=?", (self._hash(refresh),))
        conn.commit()
        conn.close()
        return self.issue_tokens()

    def valid_access(self, token: str) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM tokens WHERE token_hash=? AND kind='access'",
            (self._hash(token),),
        ).fetchone()
        conn.close()
        return bool(row and row["expires_at"] >= time.time())

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
