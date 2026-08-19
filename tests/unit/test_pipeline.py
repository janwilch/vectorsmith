"""Pipeline post_filter + group_by."""

from __future__ import annotations

import pytest

from vectorsmith_core.adapters.base import RowBatch, SearchRequest
from vectorsmith_core.api import CompiledTool
from vectorsmith_core.compilepkg.compiler import ExecutionPlan
from vectorsmith_core.errors import SchemaDriftError
from vectorsmith_core.execute.pipeline import execute_pipeline
from vectorsmith_core.ir.filter import Cond
from vectorsmith_core.tds.models import (
    GroupByBody,
    GroupByStep,
    PerGroup,
    PostFilterBody,
    PostFilterStep,
    RetrieveBody,
    RetrieveStep,
    Target,
)


class _Fake:
    async def search(self, req: SearchRequest) -> RowBatch:
        rows = [
            {"client_name": "A", "amount": 10, "paid_amount": 1, "days_overdue": 4},
            {"client_name": "A", "amount": 3, "paid_amount": 2, "days_overdue": 1},
            {"client_name": "B", "amount": 8, "paid_amount": 0, "days_overdue": 9},
        ]
        return RowBatch(rows=rows[: req.limit], exhausted=True)

    def compile_filter(self, node: object) -> object:
        return node


@pytest.mark.asyncio
async def test_pipeline_post_filter_and_group() -> None:
    steps = [
        RetrieveStep(
            retrieve=RetrieveBody(target=Target(connection="main", collection="invoices"))
        ),
        PostFilterStep(post_filter=PostFilterBody(expr="amount > paid_amount")),
        GroupByStep(
            group_by=GroupByBody(
                keys=["client_name"],
                per_group=PerGroup(sort_by="amount", desc=True, take=1),
            )
        ),
    ]
    plan = ExecutionPlan(
        kind="pipeline",
        connection="main",
        collection="invoices",
        query_param=None,
        query_required=False,
        mode="dense",
        alpha=0.5,
        embedding=None,
        fetch_k_param="limit",
        overfetch_factor=10,
        max_candidates=2000,
        projection=None,
        limit_default=10,
        limit_max=50,
        include_score=True,
        steps=steps,
    )
    compiled = CompiledTool(
        name="top_overdue",
        mcp_schema={"name": "top_overdue", "inputSchema": {"type": "object", "properties": {}}},
        plan=plan,
    )
    result = await execute_pipeline(
        compiled,
        plan,
        {},
        adapter=_Fake(),
        embed=None,
        ctx=None,
        debug=False,
    )
    assert result.count == 2
    assert {r["client_name"] for r in result.rows} == {"A", "B"}


@pytest.mark.asyncio
async def test_pipeline_drift_aborts() -> None:
    class _Bad:
        async def search(self, req: SearchRequest) -> RowBatch:
            _ = req
            return RowBatch(
                rows=[{"amount": "x", "paid_amount": 1} for _ in range(20)],
                exhausted=True,
            )

        def compile_filter(self, node: object) -> object:
            return node

    steps = [
        RetrieveStep(
            retrieve=RetrieveBody(target=Target(connection="main", collection="invoices"))
        ),
        PostFilterStep(post_filter=PostFilterBody(expr="amount > paid_amount")),
    ]
    plan = ExecutionPlan(
        kind="pipeline",
        connection="main",
        collection="invoices",
        query_param=None,
        query_required=False,
        mode="dense",
        alpha=0.5,
        embedding=None,
        fetch_k_param="limit",
        overfetch_factor=1,
        max_candidates=50,
        projection=None,
        limit_default=10,
        limit_max=50,
        include_score=True,
        static_conds=[Cond("tenant", "eq", "acme")],
        steps=steps,
    )
    compiled = CompiledTool(
        name="p",
        mcp_schema={"name": "p", "inputSchema": {"type": "object", "properties": {}}},
        plan=plan,
    )
    with pytest.raises(SchemaDriftError):
        await execute_pipeline(
            compiled, plan, {}, adapter=_Bad(), embed=None, ctx=None, debug=False
        )
