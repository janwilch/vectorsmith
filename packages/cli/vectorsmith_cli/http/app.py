"""Starlette app: /mcp, well-knowns, /oauth, /healthz."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from vectorsmith_cli.http.builtin_oauth import server as oauth
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_cli.identity import DEFAULT_SERVER_NAME, PRODUCT_NAME
from vectorsmith_cli.serve_common import (
    SERVER_INSTRUCTIONS,
    dispatch,
    expire_old_drafts,
    mcp_schemas,
)
from vectorsmith_core.api import CallContext
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.version import ENGINE_VERSION


def challenge_header(public_url: str) -> str:
    base = public_url.rstrip("/")
    return f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource"'


class BearerGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path not in {"/mcp"}:
            return await call_next(request)
        auth = request.app.state.auth_mode
        if auth == "none":
            return await call_next(request)
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        store: AuthStore = request.app.state.store
        if not token or not store.valid_access(token):
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": challenge_header(request.app.state.public_url)},
            )
        return await call_next(request)


async def healthz(_request: Request) -> Response:
    return JSONResponse({"ok": True})


def build_app(
    *,
    engine: Engine,
    enable_define: bool,
    auth: str,
    public_url: str,
    store: AuthStore,
    drafts_path: Path,
    name: str = DEFAULT_SERVER_NAME,
) -> Starlette:
    expire_old_drafts(drafts_path)
    server_name = name

    async def mcp(request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse({"ok": True})
        body = await request.json()
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params") or {}
        if method == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {
                    "name": server_name,
                    "title": PRODUCT_NAME,
                    "version": ENGINE_VERSION,
                },
                "instructions": SERVER_INSTRUCTIONS,
            }
        elif method == "tools/list":
            result = {"tools": mcp_schemas(engine.project, enable_define=enable_define)}
        elif method == "tools/call":
            name = params.get("name")
            args = dict(params.get("arguments") or {})
            payload = await dispatch(
                engine,
                name,
                args,
                ctx=CallContext(request_id=str(uuid.uuid4())),
                enable_define=enable_define,
                drafts_path=drafts_path,
            )
            result = {
                "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
                "structuredContent": payload,
            }
        elif method == "notifications/initialized":
            return JSONResponse({"jsonrpc": "2.0", "result": {}})
        else:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": method}},
                status_code=400,
            )
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})

    async def protected_resource(_request: Request) -> Response:
        return JSONResponse(oauth.well_known(public_url))

    async def as_meta(_request: Request) -> Response:
        return JSONResponse(oauth.as_metadata(public_url))

    routes = [
        Route("/healthz", healthz),
        Route("/mcp", mcp, methods=["GET", "POST"]),
        Route("/.well-known/oauth-protected-resource", protected_resource),
        Route("/.well-known/oauth-authorization-server", as_meta),
        Route("/oauth/authorize", oauth.authorize, methods=["GET", "POST"]),
        Route("/oauth/token", oauth.token, methods=["POST"]),
        Route("/oauth/register", oauth.register, methods=["POST"]),
        Route("/oauth/revoke", oauth.revoke, methods=["POST"]),
    ]
    app = Starlette(routes=routes, middleware=[])
    app.add_middleware(BearerGate)
    app.state.engine = engine
    app.state.store = store
    app.state.auth_mode = auth
    app.state.public_url = public_url
    return app
