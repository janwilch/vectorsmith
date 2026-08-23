"""GET /readyz and drain-gate behaviour."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from vectorsmith_cli.http.app import build_app
from vectorsmith_cli.http.auth.jwt import JWTProvider
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_core.api import EnvCredentialResolver, HealthStatus, load_project
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.tds.models import JWTAuthConfig


def _engine() -> Engine:
    project = load_project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                    "kind": "lookup",
                }
            ],
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    return Engine(project, credential_resolver=EnvCredentialResolver({}))


def _app(tmp_path: Path, engine: Engine, *, auth: str = "none", provider: Any = None) -> TestClient:
    return TestClient(
        build_app(
            engine=engine,
            enable_define=False,
            auth=auth,
            public_url="https://example.test",
            store=AuthStore(tmp_path / "auth.db"),
            drafts_path=tmp_path / "tools.drafts.yaml",
            auth_provider=provider,
        )
    )


def test_readyz_503_when_connection_down(tmp_path: Path, monkeypatch: Any) -> None:
    engine = _engine()

    async def down() -> dict[str, HealthStatus]:
        return {"main": HealthStatus(ok=False, detail="qdrant down", latency_ms=12)}

    monkeypatch.setattr(engine, "health", down)
    client = _app(tmp_path, engine)
    res = client.get("/readyz")
    assert res.status_code == 503
    body = res.json()
    assert body["ready"] is False
    assert body["connections"]["main"]["ok"] is False


def test_drain_rejects_new_mcp(tmp_path: Path) -> None:
    client = _app(tmp_path, _engine())
    client.app.state.draining = True
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert res.status_code == 503
    assert res.json()["error"] == "shutting_down"
    assert client.get("/healthz").status_code == 200


def test_jwt_readyz_fetches_jwks(tmp_path: Path, monkeypatch: Any) -> None:
    provider = JWTProvider(JWTAuthConfig(jwks_url="https://auth.example.com/jwks.json"))

    async def healthy() -> bool:
        return True

    monkeypatch.setattr(provider, "health", healthy)
    engine = _engine()

    async def up() -> dict[str, HealthStatus]:
        return {"main": HealthStatus(ok=True, detail="ok", latency_ms=1)}

    monkeypatch.setattr(engine, "health", up)
    client = _app(tmp_path, engine, auth="jwt", provider=provider)
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["auth"] == {"ok": True, "provider": "jwt"}


def test_jwt_readyz_503_when_jwks_down(tmp_path: Path, monkeypatch: Any) -> None:
    provider = JWTProvider(JWTAuthConfig(jwks_url="https://auth.example.com/jwks.json"))

    async def unhealthy() -> bool:
        return False

    monkeypatch.setattr(provider, "health", unhealthy)
    engine = _engine()

    async def up() -> dict[str, HealthStatus]:
        return {"main": HealthStatus(ok=True, detail="ok", latency_ms=1)}

    monkeypatch.setattr(engine, "health", up)
    client = _app(tmp_path, engine, auth="jwt", provider=provider)
    res = client.get("/readyz")
    assert res.status_code == 503
    assert res.json()["auth"]["ok"] is False
