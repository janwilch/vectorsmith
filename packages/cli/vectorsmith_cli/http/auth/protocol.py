"""Auth provider protocol used by HTTP ``/mcp``."""

from __future__ import annotations

from typing import Protocol

from starlette.requests import Request

from vectorsmith_core.api import CallContext


class AuthProvider(Protocol):
    async def authenticate(self, request: Request) -> CallContext: ...

    async def health(self) -> bool: ...
