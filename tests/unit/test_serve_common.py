"""Live catalog meta-tools (Desktop ignores tools/list_changed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vectorsmith_cli.serve_common import dispatch, mcp_schemas
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.execute.engine import Engine


def _project():
    return load_project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                }
            ],
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    )


def test_live_catalog_first_in_mcp_schemas() -> None:
    names = [s["name"] for s in mcp_schemas(_project(), enable_define=False)]
    assert names[:2] == ["list_available_tools", "run_tool"]
    assert "search_invoices" in names


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
