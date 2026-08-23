"""tool.rerank — retrieve_k then rerank; failure keeps vector order."""

from __future__ import annotations

from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch, SearchRequest
from vectorsmith_core.api import CallContext, load_project
from vectorsmith_core.execute.rerank import clear_cross_encoder_cache, resolve_rerank_provider
from vectorsmith_core.execute.single_step import execute_single


def _src(*, rerank: dict[str, Any] | None = None) -> dict[str, Any]:
    tool: dict[str, Any] = {
        "name": "search_invoices",
        "description": "Search invoices by client status and due date for billing.",
        "target": {"connection": "main", "collection": "invoices"},
        "query": {"param": "query"},
        "output": {"limit_default": 2, "limit_max": 10},
    }
    if rerank is not None:
        tool["rerank"] = rerank
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "tools": [tool],
    }


def test_cross_encoder_provider_is_distinct() -> None:
    provider = resolve_rerank_provider("cross_encoder")
    assert type(provider).__name__ == "_CrossEncoderRerank"


@pytest.mark.asyncio
async def test_cross_encoder_caches_and_uses_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[str] = []

    class FakeEnc:
        def __init__(self, model: str) -> None:
            created.append(model)

        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            return [float(i) for i in range(len(pairs))]

    import types

    mod = types.ModuleType("sentence_transformers")
    mod.CrossEncoder = FakeEnc  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", mod)
    clear_cross_encoder_cache()
    provider = resolve_rerank_provider("cross_encoder")
    spec = type("S", (), {"model": "unit-ce", "config": {}})()
    rows = [{"title": "a"}, {"title": "b"}]
    first = await provider.rerank("q", rows, spec=spec)
    second = await provider.rerank("q", rows, spec=spec)
    assert created == ["unit-ce"]
    assert [r["title"] for r in first] == ["b", "a"]
    assert [r["title"] for r in second] == ["b", "a"]
    clear_cross_encoder_cache()


def test_unknown_rerank_provider_errors() -> None:
    with pytest.raises(RuntimeError, match="unknown rerank provider"):
        resolve_rerank_provider("not-a-provider")


def test_rerank_disabled_by_default() -> None:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.rerank is not None
    assert plan.rerank.enabled is False


@pytest.mark.asyncio
async def test_retrieve_k_then_rerank_to_limit() -> None:
    project = load_project(
        _src(rerank={"enabled": True, "provider": "http", "retrieve_k": 5}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    compiled = project.tools["search_invoices"]
    plan = compiled.plan
    assert plan is not None
    assert plan.rerank is not None

    async def _rerank(query: str, rows: list[dict[str, Any]], *, spec: Any) -> list[dict[str, Any]]:
        return list(reversed(rows))

    plan.rerank._rerank = _rerank
    captured: list[int] = []

    class Fake:
        async def search(self, req: SearchRequest) -> RowBatch:
            captured.append(req.limit)
            return RowBatch(
                rows=[{"_id": str(i), "title": str(i), "_score": 1.0 - i * 0.1} for i in range(5)]
            )

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1]]

    out = await execute_single(
        compiled,
        plan,
        {"query": "x", "limit": 2},
        adapter=Fake(),  # type: ignore[arg-type]
        embed=Embed(),  # type: ignore[arg-type]
        ctx=CallContext(request_id="t"),
    )
    assert captured == [5]
    assert [r["_id"] for r in out.rows] == ["4", "3"]


@pytest.mark.asyncio
async def test_rerank_failure_keeps_vector_order() -> None:
    project = load_project(
        _src(rerank={"enabled": True, "retrieve_k": 4}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    compiled = project.tools["search_invoices"]
    plan = compiled.plan
    assert plan is not None
    assert plan.rerank is not None

    async def boom(query: str, rows: list[dict[str, Any]], *, spec: Any) -> list[dict[str, Any]]:
        raise RuntimeError("rerank down")

    plan.rerank._rerank = boom

    class Fake:
        async def search(self, req: SearchRequest) -> RowBatch:
            return RowBatch(
                rows=[
                    {"_id": "a", "_score": 0.9},
                    {"_id": "b", "_score": 0.8},
                    {"_id": "c", "_score": 0.7},
                ]
            )

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1]]

    out = await execute_single(
        compiled,
        plan,
        {"query": "x", "limit": 2},
        adapter=Fake(),  # type: ignore[arg-type]
        embed=Embed(),  # type: ignore[arg-type]
        ctx=CallContext(request_id="t"),
    )
    assert [r["_id"] for r in out.rows] == ["a", "b"]
    assert "VB4031" in out.warnings
