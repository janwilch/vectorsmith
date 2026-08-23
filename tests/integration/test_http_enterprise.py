"""HTTP JWT → tenancy filter; wrong tenant is rejected or empty."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from vectorsmith_cli.http.app import build_app
from vectorsmith_cli.http.auth.jwt import JWTProvider
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import EnvCredentialResolver, load_project
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.ir.filter import And, Cond, IRNode
from vectorsmith_core.tds.models import JWTAuthConfig


def _rsa_jwt() -> tuple[Any, Any, dict[str, Any]]:
    jwt = pytest.importorskip("jwt")
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "k1"
    return key, jwt, {"keys": [jwk]}


def _token(jwt: Any, key: Any, *, extra: dict[str, Any] | None = None) -> str:
    payload = {
        "sub": "user-1",
        "tenant_id": "acme",
        "iss": "https://auth.example.com",
        "aud": "vectorsmith",
        "exp": int(time.time()) + 60,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "k1"})


def _tenant_eq(node: object, path: str, value: str) -> bool:
    if isinstance(node, Cond):
        return node.path == path and node.op == "eq" and node.value == value
    if isinstance(node, And):
        return any(_tenant_eq(c, path, value) for c in node.children)
    return False


class _Fake:
    def __init__(self) -> None:
        self.filter_ir: IRNode | None = None
        self.rows = [{"tenant": "acme", "id": "kept"}]

    def compile_filter(self, node: IRNode | None) -> object:
        return node

    async def search(self, req: Any) -> RowBatch:
        self.filter_ir = req.filter_ir
        return RowBatch(rows=list(self.rows), exhausted=True)


def _client(tmp_path: Path, fake: _Fake, provider: JWTProvider) -> TestClient:
    project = load_project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
            "security": {
                "tenancy": {"mode": "claim", "claim": "tenant_id", "path": "tenant"},
                "auth": {"mode": "jwt", "jwt": {"issuer": "https://auth.example.com"}},
            },
            "observability": {"audit": {"enabled": True}},
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                }
            ],
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))

    async def _adapter(_name: str) -> _Fake:
        return fake

    engine._adapter = _adapter  # type: ignore[method-assign]
    app = build_app(
        engine=engine,
        enable_define=False,
        include_meta=False,
        auth="jwt",
        public_url="https://example.test",
        store=AuthStore(tmp_path / "auth.db"),
        drafts_path=tmp_path / "tools.drafts.yaml",
        auth_provider=provider,
    )
    return TestClient(app)


def test_jwt_tenancy_filters_to_claim(tmp_path: Path) -> None:
    key, jwt, jwks = _rsa_jwt()
    provider = JWTProvider(
        JWTAuthConfig(issuer="https://auth.example.com", audience="vectorsmith"),
        jwks=jwks,
    )
    fake = _Fake()
    client = _client(tmp_path, fake, provider)
    token = _token(jwt, key)
    res = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_invoices", "arguments": {}},
        },
    )
    assert res.status_code == 200
    assert _tenant_eq(fake.filter_ir, "tenant", "acme")
    payload = res.json()["result"]["structuredContent"]
    assert payload["count"] == 1


def test_missing_tenant_claim_is_forbidden(tmp_path: Path) -> None:
    key, jwt, jwks = _rsa_jwt()
    provider = JWTProvider(
        JWTAuthConfig(issuer="https://auth.example.com", audience="vectorsmith"),
        jwks=jwks,
    )
    fake = _Fake()
    client = _client(tmp_path, fake, provider)
    token = _token(jwt, key, extra={"tenant_id": None})
    # overwrite claim to empty
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": "https://auth.example.com",
            "aud": "vectorsmith",
            "exp": 9_999_999_999,
        },
        key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    res = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search_invoices", "arguments": {}},
        },
    )
    assert res.status_code in {403, 401}
    assert fake.filter_ir is None


@pytest.mark.asyncio
async def test_audit_emits_on_http_tool_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vectorsmith_cli.serve_common import dispatch
    from vectorsmith_core.api import CallContext

    events: list[dict[str, Any]] = []

    class Sink:
        async def emit(self, event: dict[str, Any]) -> None:
            events.append(event)

        async def flush(self) -> None:
            return None

    project = load_project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
            "observability": {"audit": {"enabled": True}},
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                }
            ],
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    engine = Engine(
        project, credential_resolver=EnvCredentialResolver({}), audit_sink=Sink()
    )
    fake = _Fake()

    async def _adapter(_name: str) -> _Fake:
        return fake

    monkeypatch.setattr(engine, "_adapter", _adapter)
    await dispatch(
        engine,
        "search_invoices",
        {},
        ctx=CallContext(request_id="http-1", principal="alice"),
        enable_define=False,
        drafts_path=tmp_path / "d.yaml",
        include_meta=False,
    )
    assert len(events) == 1
    assert events[0]["status"] == "ok"
    assert events[0]["tool"] == "search_invoices"
