"""query.expand — off by default; N+1 merge; failure warning."""

from __future__ import annotations

from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch, SearchRequest
from vectorsmith_core.api import CallContext, load_project
from vectorsmith_core.execute.single_step import execute_single


def _src(*, expand: dict[str, Any] | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"param": "query"}
    if expand is not None:
        query["expand"] = expand
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "query": query,
            }
        ],
    }


def test_expand_disabled_by_default() -> None:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.expand is not None
    assert plan.expand.enabled is False


@pytest.mark.asyncio
async def test_expand_embeds_variants_and_merges_best_score() -> None:
    project = load_project(
        _src(expand={"enabled": True, "provider": "none", "variants": 2}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    compiled = project.tools["search_invoices"]
    plan = compiled.plan
    assert plan is not None
    assert plan.expand is not None

    async def _expand(query: str, *, spec: Any) -> list[str]:
        return ["alt phrasing"]

    plan.expand._expand = _expand
    seen: list[str] = []

    class Fake:
        async def search(self, req: SearchRequest) -> RowBatch:
            seen.append(str(req.query_text))
            if req.query_text == "orig":
                return RowBatch(rows=[{"_id": "a", "title": "orig", "_score": 0.4}])
            return RowBatch(rows=[{"_id": "a", "title": "alt", "_score": 0.9}])

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1, 0.2, 0.3]]

    out = await execute_single(
        compiled,
        plan,
        {"query": "orig"},
        adapter=Fake(),  # type: ignore[arg-type]
        embed=Embed(),  # type: ignore[arg-type]
        ctx=CallContext(request_id="t"),
    )
    assert seen == ["orig", "alt phrasing"]
    assert len(out.rows) == 1
    assert out.rows[0]["_score"] == 0.9
    assert out.rows[0]["title"] == "alt"


@pytest.mark.asyncio
async def test_expand_failure_falls_back() -> None:
    project = load_project(
        _src(expand={"enabled": True, "provider": "openai", "variants": 2}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    compiled = project.tools["search_invoices"]
    plan = compiled.plan
    assert plan is not None
    assert plan.expand is not None

    async def boom(query: str, *, spec: Any) -> list[str]:
        raise RuntimeError("llm down")

    plan.expand._expand = boom
    seen: list[str] = []

    class Fake:
        async def search(self, req: SearchRequest) -> RowBatch:
            seen.append(str(req.query_text))
            return RowBatch(rows=[{"_id": "a", "_score": 0.5}])

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1]]

    out = await execute_single(
        compiled,
        plan,
        {"query": "orig"},
        adapter=Fake(),  # type: ignore[arg-type]
        embed=Embed(),  # type: ignore[arg-type]
        ctx=CallContext(request_id="t"),
    )
    assert seen == ["orig"]
    assert "VB4030" in out.warnings
