"""API key file lookup → principal + claims."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from starlette.requests import Request

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import AuthError
from vectorsmith_core.tds.models import APIKeyAuthConfig


class APIKeyProvider:
    def __init__(self, cfg: APIKeyAuthConfig, keys: dict[str, dict[str, Any]]) -> None:
        self.cfg = cfg
        self.keys = keys

    @classmethod
    def from_file(cls, cfg: APIKeyAuthConfig) -> APIKeyProvider:
        if not cfg.keys_file:
            raise AuthError(detail="api_key.keys_file is required")
        path = Path(cfg.keys_file)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AuthError(detail=f"cannot read api keys file: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AuthError(detail="api keys file is not valid JSON") from exc
        if not isinstance(raw, dict):
            raise AuthError(detail="api keys file must be a JSON object")
        keys: dict[str, dict[str, Any]] = {}
        for key, rec in raw.items():
            if isinstance(rec, dict):
                keys[str(key)] = rec
        return cls(cfg, keys)

    def _presented(self, request: Request) -> str:
        want = self.cfg.header.lower()
        raw = ""
        for name, val in request.headers.items():
            if name.lower() == want:
                raw = val
                break
        if not raw:
            return ""
        scheme = self.cfg.scheme
        if scheme == "Bearer" and raw.lower().startswith("bearer "):
            return raw[7:].strip()
        if scheme == "ApiKey" and raw.lower().startswith("apikey "):
            return raw[7:].strip()
        return raw.strip()

    async def authenticate(self, request: Request) -> CallContext:
        token = self._presented(request)
        rec = self.keys.get(token)
        if rec is None:
            raise AuthError(detail="invalid api key")
        claims = rec.get("claims") if isinstance(rec.get("claims"), dict) else {}
        principal = rec.get("principal")
        return CallContext(
            request_id=str(uuid.uuid4()),
            principal=str(principal) if principal is not None else None,
            claims=dict(claims),
        )

    async def health(self) -> bool:
        return bool(self.keys)
