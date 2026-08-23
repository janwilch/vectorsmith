"""Credential backends: env default + vault cache."""

from __future__ import annotations

import pytest

from vectorsmith_core.api import EnvCredentialResolver, load_project
from vectorsmith_core.errors import MissingEnvError
from vectorsmith_core.security.credentials import (
    AwsSmCredentialResolver,
    CompositeCredentialResolver,
    K8sCredentialResolver,
    VaultCredentialResolver,
    build_credential_resolver,
)
from vectorsmith_core.tds.models import AwsSmSpec, K8sSpec, QdrantConn, VaultCredSpec


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


@pytest.mark.asyncio
async def test_composite_dispatches_vault() -> None:
    async def fetch(_vault: VaultCredSpec) -> dict[str, str]:
        return {"url": "http://from-vault"}

    res = build_credential_resolver({}, vault_fetch=fetch)
    spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "vault", "vault": {"path": "secret/data/q"}},  # type: ignore[arg-type]
    )
    got = await res.resolve("main", spec)
    assert got.values["url"] == "http://from-vault"


@pytest.mark.asyncio
async def test_aws_sm_fetch_and_cache() -> None:
    calls = {"n": 0}

    async def fetch(spec: AwsSmSpec) -> dict[str, str]:
        calls["n"] += 1
        assert spec.secret_id == "prod/qdrant"  # noqa: S105
        return {"url": "http://from-sm", "api_key": "k"}

    res = AwsSmCredentialResolver(fetch=fetch, ttl_s=60)
    spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "aws_sm", "aws_sm": {"secret_id": "prod/qdrant"}},  # type: ignore[arg-type]
    )
    a = await res.resolve("main", spec)
    b = await res.resolve("main", spec)
    assert a.values["url"] == "http://from-sm"
    assert b.values["api_key"] == "k"
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_k8s_fetch() -> None:
    async def fetch(spec: K8sSpec) -> dict[str, str]:
        assert spec.secret == "qdrant"  # noqa: S105
        return {"url": "http://from-k8s"}

    res = K8sCredentialResolver(fetch=fetch)
    spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "k8s", "k8s": {"secret": "qdrant"}},  # type: ignore[arg-type]
    )
    got = await res.resolve("main", spec)
    assert got.values["url"] == "http://from-k8s"


@pytest.mark.asyncio
async def test_composite_env_still_default() -> None:
    res = CompositeCredentialResolver({"QDRANT_URL": "http://env"})
    spec = QdrantConn(backend="qdrant", url="${QDRANT_URL}")
    got = await res.resolve("main", spec)
    assert got.values["url"] == "http://env"


def test_missing_aws_sm_secret_id_is_vb4041() -> None:
    project = load_project(
        {
            "tds_version": "1",
            "connections": {
                "main": {
                    "backend": "qdrant",
                    "url": "http://localhost:6333",
                    "credentials": {"provider": "aws_sm"},
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
    assert any(i.code == "VB4041" for i in project.issues)


def test_missing_k8s_secret_is_vb4042() -> None:
    project = load_project(
        {
            "tds_version": "1",
            "connections": {
                "main": {
                    "backend": "qdrant",
                    "url": "http://localhost:6333",
                    "credentials": {"provider": "k8s"},
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
    assert any(i.code == "VB4042" for i in project.issues)
