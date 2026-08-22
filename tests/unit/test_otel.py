"""Observability tracing/metrics — off by default, increment when on."""

from __future__ import annotations

from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch, SearchRequest
from vectorsmith_core.api import CallContext, load_project
from vectorsmith_core.execute.single_step import execute_single
from vectorsmith_core.observe import metrics as metrics_mod
from vectorsmith_core.observe import tracing


def _src() -> dict[str, Any]:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "query": {"param": "query"},
            }
        ],
    }


def test_tracing_disabled_records_nothing() -> None:
    tracing.configure_tracing(False)
    tracing.reset_spans()
    with tracing.start_span("vectorsmith.tool.call"):
        with tracing.start_span("vectorsmith.embed"):
            pass
    assert tracing.recorded_spans() == []


def test_metrics_disabled_is_noop() -> None:
    metrics_mod.configure_metrics(False)
    metrics_mod.reset()
    metrics_mod.inc_tool_call("search_invoices", "ok")
    assert metrics_mod.snapshot()["calls"] == {}


def test_metrics_increment_when_enabled() -> None:
    metrics_mod.configure_metrics(True)
    metrics_mod.reset()
    metrics_mod.inc_tool_call("search_invoices", "ok")
    metrics_mod.inc_tool_call("search_invoices", "error")
    snap = metrics_mod.snapshot()
    assert snap["calls"][("search_invoices", "ok")] == 1
    assert snap["calls"][("search_invoices", "error")] == 1
    text = metrics_mod.render()
    assert "vectorsmith_tool_calls_total" in text
    metrics_mod.configure_metrics(False)


@pytest.mark.asyncio
async def test_spans_nest_call_embed_search() -> None:
    tracing.configure_tracing(True)
    tracing.reset_spans()
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    compiled = project.tools["search_invoices"]
    plan = compiled.plan
    assert plan is not None

    class Fake:
        async def search(self, req: SearchRequest) -> RowBatch:
            return RowBatch(rows=[])

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1]]

    with tracing.start_span("vectorsmith.tool.call", tool="search_invoices"):
        await execute_single(
            compiled,
            plan,
            {"query": "x"},
            adapter=Fake(),  # type: ignore[arg-type]
            embed=Embed(),  # type: ignore[arg-type]
            ctx=CallContext(request_id="t"),
        )
    names = [n for n, _ in tracing.recorded_spans()]
    assert names[0] == "vectorsmith.tool.call"
    assert "vectorsmith.embed" in names
    assert "vectorsmith.adapter.search" in names
    tracing.configure_tracing(False)
    tracing.reset_spans()
