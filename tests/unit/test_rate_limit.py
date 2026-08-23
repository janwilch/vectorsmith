"""security.rate_limit (disabled by default)."""

from __future__ import annotations

from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import RateLimited
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.security.rate_limit import RedisRateLimiter


def _src(*, rate: dict[str, Any]) -> dict[str, Any]:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "security": {"rate_limit": rate},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
            }
        ],
    }


def _engine(src: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Engine:
    project = load_project(src, env={"QDRANT_URL": "http://localhost:6333"})
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))

    class Fake:
        def compile_filter(self, node: object) -> object:
            return node

        async def search(self, req: Any) -> RowBatch:
            _ = req
            return RowBatch(rows=[], exhausted=True)

    async def _adapter(_name: str) -> Fake:
        return Fake()

    monkeypatch.setattr(engine, "_adapter", _adapter)
    return engine


def test_disabled_by_default() -> None:
    project = load_project(
        _src(rate={}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    assert project.tds.security.rate_limit.enabled is False


@pytest.mark.asyncio
async def test_31st_request_in_window(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(
        _src(rate={"enabled": True, "per_tool": {"search_invoices": "30/minute"}}),
        monkeypatch,
    )
    ctx = CallContext(request_id="t", principal="alice")
    for _ in range(30):
        await engine.call("search_invoices", {}, ctx=ctx)
    with pytest.raises(RateLimited) as exc:
        await engine.call("search_invoices", {}, ctx=ctx)
    assert exc.value.retry_after_s >= 1
    assert "search_invoices" in exc.value.detail


@pytest.mark.asyncio
async def test_principals_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(
        _src(rate={"enabled": True, "per_principal": {"requests_per_minute": 2}}),
        monkeypatch,
    )
    a = CallContext(request_id="a", principal="alice")
    b = CallContext(request_id="b", principal="bob")
    await engine.call("search_invoices", {}, ctx=a)
    await engine.call("search_invoices", {}, ctx=a)
    with pytest.raises(RateLimited):
        await engine.call("search_invoices", {}, ctx=a)
    await engine.call("search_invoices", {}, ctx=b)


class _IncrRedis:
    def __init__(self, data: dict[str, int]) -> None:
        self.data = data

    def incr(self, key: str) -> int:
        self.data[key] = int(self.data.get(key) or 0) + 1
        return self.data[key]

    def expire(self, key: str, _s: int) -> None:
        _ = key

    def ttl(self, key: str) -> int:
        _ = key
        return 12


class _AsyncIncrRedis:
    def __init__(self, data: dict[str, int]) -> None:
        self.data = data

    async def incr(self, key: str) -> int:
        self.data[key] = int(self.data.get(key) or 0) + 1
        return self.data[key]

    async def expire(self, key: str, _s: int) -> None:
        _ = key

    async def ttl(self, key: str) -> int:
        _ = key
        return 8


@pytest.mark.asyncio
async def test_redis_async_client_does_not_use_thread() -> None:
    shared: dict[str, int] = {}
    limiter = RedisRateLimiter(client=_AsyncIncrRedis(shared))
    assert limiter._async is True
    await limiter.check("alice:search_invoices", 1, 60)
    with pytest.raises(RateLimited) as exc:
        await limiter.check("alice:search_invoices", 1, 60)
    assert exc.value.retry_after_s == 8


@pytest.mark.asyncio
async def test_redis_store_shared_across_replicas() -> None:
    shared: dict[str, int] = {}
    a = RedisRateLimiter(client=_IncrRedis(shared))
    b = RedisRateLimiter(client=_IncrRedis(shared))
    await a.check("alice:search_invoices", 2, 60)
    await b.check("alice:search_invoices", 2, 60)
    with pytest.raises(RateLimited):
        await a.check("alice:search_invoices", 2, 60)
