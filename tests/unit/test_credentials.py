"""Credential backends: env default + vault cache."""

from __future__ import annotations

import pytest

from vectorsmith_core.api import EnvCredentialResolver, load_project
from vectorsmith_core.errors import MissingEnvError
from vectorsmith_core.security.credentials import VaultCredentialResolver
from vectorsmith_core.tds.models import QdrantConn, VaultCredSpec


@pytest.mark.asyncio
async def test_env_resolver_default() -> None:
    res = EnvCredentialResolver({"QDRANT_URL": "http://q"})
    spec = QdrantConn(backend="qdrant", url="${QDRANT_URL}")
    got = await res.resolve("main", spec)
    assert got.values["url"] == "http://q"
    assert "http://q" not in repr(got)


@pytest.mark.asyncio
async def test_vault_fetches_and_caches() -> None:
    calls = {"n": 0}

    async def fetch(vault: VaultCredSpec) -> dict[str, str]:
        calls["n"] += 1
        _ = vault
        return {"url": "http://from-vault", "api_key": "k"}

    res = VaultCredentialResolver(fetch=fetch, ttl_s=60)
    spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "vault", "vault": {"path": "secret/data/qdrant"}},  # type: ignore[arg-type]
    )
    a = await res.resolve("main", spec)
    b = await res.resolve("main", spec)
    assert a.values["url"] == "http://from-vault"
    assert b.values["url"] == "http://from-vault"
    assert calls["n"] == 1
    assert "from-vault" not in repr(a)


@pytest.mark.asyncio
async def test_vault_missing_secret() -> None:
    async def fetch(_vault: VaultCredSpec) -> dict[str, str]:
        return {}

    res = VaultCredentialResolver(fetch=fetch)
    spec = QdrantConn(
        backend="qdrant",
        url="http://localhost:6333",
        credentials={"provider": "vault", "vault": {"path": "secret/data/missing"}},  # type: ignore[arg-type]
    )
    with pytest.raises(MissingEnvError) as exc:
        await res.resolve("main", spec)
    assert "secret/data/missing" in exc.value.detail


def test_credentials_block_loads() -> None:
    project = load_project(
        {
            "tds_version": "1",
            "connections": {
                "main": {
                    "backend": "qdrant",
                    "url": "http://localhost:6333",
                    "credentials": {"provider": "env"},
                }
            },
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                }
            ],
        },
        env={},
    )
    assert project.tds.connections["main"].credentials.provider == "env"
