"""Existing builtin OAuth bearer tokens (SQLite / Redis store)."""

from __future__ import annotations

import uuid
from typing import Any

from starlette.requests import Request

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import AuthError


class BuiltinOAuthProvider:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def authenticate(self, request: Request) -> CallContext:
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        if not token or not self.store.valid_access(token):
            raise AuthError(detail="authentication failed")
        return CallContext(request_id=str(uuid.uuid4()), principal="builtin")

    async def health(self) -> bool:
        return True
