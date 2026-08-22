"""Request deadlines → QueryTimeout."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch, SearchRequest
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import QueryTimeout
from vectorsmith_core.execute.engine import Engine


@pytest.mark.asyncio
async def test_deadline_raises_query_timeout() -> None:
    project = load_project(
        {
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
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))

    class Slow:
        async def search(self, req: SearchRequest) -> RowBatch:
            await asyncio.sleep(1)
            return RowBatch(rows=[])

        def compile_filter(self, node: object) -> object:
            return node

    class Embed:
        async def embed(self, texts: list[str], model: str, *, config: Any = None):
            return [[0.1]]

    async def _adapter(_name: str) -> Any:
        return Slow()

    engine._adapter = _adapter  # type: ignore[method-assign]
    engine._embed_for = lambda _plan: Embed()  # type: ignore[method-assign]
    with pytest.raises(QueryTimeout):
        await engine.call(
            "search_invoices",
            {"query": "x"},
            ctx=CallContext(request_id="t", deadline_s=0.05),
        )
