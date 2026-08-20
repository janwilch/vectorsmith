"""Live catalog meta-tools (Desktop ignores tools/list_changed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vectorsmith_cli.serve_common import dispatch, mcp_schemas
from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.ir.filter import And, Cond, IRNode


def _src() -> dict[str, Any]:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "static_filters": [{"path": "tenant", "op": "eq", "value": "acme"}],
                "parameters": [
                    {
                        "name": "status",
                        "path": "status",
                        "dtype": "keyword",
                        "op": "eq",
                        "enum": ["draft", "sent", "paid", "overdue"],
                    }
                ],
            }
        ],
    }


def _project():
    return load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})


class _FakeAdapter:
    def __init__(self) -> None:
        self.filter_ir: IRNode | None = None

    def compile_filter(self, node: IRNode | None) -> object:
        return node

    async def search(self, req: Any) -> RowBatch:
        self.filter_ir = req.filter_ir  # type: ignore[assignment]
        return RowBatch(rows=[], exhausted=True)


def _tenant_eq(node: object, value: str = "acme") -> bool:
    if isinstance(node, Cond):
        return node.path == "tenant" and node.op == "eq" and node.value == value
    if isinstance(node, And):
        return any(_tenant_eq(c, value) for c in node.children)
    return False


def test_live_catalog_first_in_mcp_schemas() -> None:
    names = [s["name"] for s in mcp_schemas(_project(), enable_define=False)]
    assert names[:2] == ["list_available_tools", "run_tool"]
    assert "search_invoices" in names


def test_no_meta_tools_omits_dispatchers() -> None:
    names = [
        s["name"]
        for s in mcp_schemas(_project(), enable_define=False, include_meta=False)
    ]
    assert "list_available_tools" not in names
    assert "run_tool" not in names
    assert names == ["search_invoices"]


@pytest.mark.asyncio
async def test_list_available_tools_dispatch(tmp_path: Path) -> None:
    project = _project()
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    out = await dispatch(
        engine,
        "list_available_tools",
        {},
        ctx=CallContext(request_id="t"),
        enable_define=False,
        drafts_path=tmp_path / "tools.drafts.yaml",
    )
    names = [row["name"] for row in out["rows"]]
    assert "search_invoices" in names
    assert "list_available_tools" not in names
    assert "run_tool" not in names


@pytest.mark.asyncio
async def test_run_tool_rejects_self(tmp_path: Path) -> None:
    project = _project()
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    out = await dispatch(
        engine,
        "run_tool",
        {"name": "run_tool", "arguments": {}},
        ctx=CallContext(request_id="t"),
        enable_define=False,
        drafts_path=tmp_path / "tools.drafts.yaml",
    )
    assert "cannot call itself" in out["message"]


@pytest.mark.asyncio
async def test_run_tool_rejects_enum_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_tool is not a jsonschema bypass — bad enum fails before the store."""
    project = _project()
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    fake = _FakeAdapter()

    async def _adapter(_name: str) -> _FakeAdapter:
        return fake

    monkeypatch.setattr(engine, "_adapter", _adapter)
    with pytest.raises(InvalidArgumentsError):
        await dispatch(
            engine,
            "run_tool",
            {"name": "search_invoices", "arguments": {"status": "not-an-enum"}},
            ctx=CallContext(request_id="t"),
            enable_define=False,
            drafts_path=tmp_path / "tools.drafts.yaml",
        )
    assert fake.filter_ir is None


@pytest.mark.asyncio
async def test_run_tool_keeps_static_tenant_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project()
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert any(c.path == "tenant" and c.value == "acme" for c in plan.static_conds)

    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    fake = _FakeAdapter()

    async def _adapter(_name: str) -> _FakeAdapter:
        return fake

    monkeypatch.setattr(engine, "_adapter", _adapter)
    await dispatch(
        engine,
        "run_tool",
        {"name": "search_invoices", "arguments": {"status": "paid"}},
        ctx=CallContext(request_id="t"),
        enable_define=False,
        drafts_path=tmp_path / "tools.drafts.yaml",
    )
    assert _tenant_eq(fake.filter_ir)


@pytest.mark.asyncio
async def test_no_meta_run_tool_is_unknown(tmp_path: Path) -> None:
    project = _project()
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    with pytest.raises(InvalidArgumentsError, match="unknown tool"):
        await dispatch(
            engine,
            "run_tool",
            {"name": "search_invoices", "arguments": {}},
            ctx=CallContext(request_id="t"),
            enable_define=False,
            drafts_path=tmp_path / "tools.drafts.yaml",
            include_meta=False,
        )
