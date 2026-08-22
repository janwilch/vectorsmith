"""``--auth none`` (localhost only; gate is in ``serve_http``)."""

from __future__ import annotations

import uuid

from starlette.requests import Request

from vectorsmith_core.api import CallContext


class NoneAuthProvider:
    async def authenticate(self, request: Request) -> CallContext:
        _ = request
        return CallContext(request_id=str(uuid.uuid4()))

    async def health(self) -> bool:
        return True
