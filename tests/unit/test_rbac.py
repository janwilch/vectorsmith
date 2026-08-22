"""security.rbac tool allow/deny lists."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vectorsmith_cli.serve_common import dispatch
from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import AuthError
from vectorsmith_core.execute.engine import Engine


def _src(*, rbac: dict[str, Any]) -> dict[str, Any]:
    tools = [
        {
            "name": "search_invoices",
            "description": "Search invoices by client status and due date for billing.",
            "target": {"connection": "main", "collection": "invoices"},
        },
        {
            "name": "count_invoices",
            "kind": "count",
            "description": "Count invoices matching filters for billing reports only.",
            "target": {"connection": "main", "collection": "invoices"},
        },
    ]
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "security": {"rbac": rbac},
        "tools": tools,
    }


VIEWER = {
    "enabled": True,
    "default_role": "viewer",
    "role_claim": "roles",
    "roles": {
        "viewer": {"allow": ["search_invoices"]},
        "admin": {"allow": ["*"]},
    },
    "deny_tools": ["define_tool"],
}


def _project(rbac: dict[str, Any] | None = None):
    return load_project(
        _src(rbac=rbac or VIEWER),
        env={"QDRANT_URL": "http://localhost:6333"},
    )


def _engine(project: Any, monkeypatch: pytest.MonkeyPatch) -> Engine:
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))

    class Fake:
        def compile_filter(self, node: object) -> object:
            return node

        async def search(self, req: Any) -> RowBatch:
            _ = req
            return RowBatch(rows=[], exhausted=True)

        async def count(self, collection: str, filter_ir: object) -> int:
            _ = collection, filter_ir
            return 0

    async def _adapter(_name: str) -> Fake:
        return Fake()

    monkeypatch.setattr(engine, "_adapter", _adapter)
    return engine


def test_rbac_off_by_default() -> None:
    project = load_project(
        _src(rbac={"enabled": False}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    assert not project.tds.security.rbac.enabled
    assert not any(i.code in {"VB4013", "VB4014"} for i in project.issues)


def test_vb4013_enabled_without_roles() -> None:
    project = _project({"enabled": True, "roles": {}})
    assert any(i.code == "VB4013" for i in project.issues)


def test_vb4014_unknown_tool() -> None:
    project = _project(
        {
            "enabled": True,
            "roles": {"viewer": {"allow": ["not_a_real_tool"]}},
        }
    )
    assert any(i.code == "VB4014" and i.severity == "warning" for i in project.issues)


@pytest.mark.asyncio
async def test_viewer_cannot_call_admin_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(_project(), monkeypatch)
    ctx = CallContext(request_id="t", claims={"roles": ["viewer"]})
    with pytest.raises(AuthError, match="not permitted"):
        await engine.call("count_invoices", {}, ctx=ctx)
    await engine.call("search_invoices", {}, ctx=ctx)


@pytest.mark.asyncio
async def test_deny_tools_blocks_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rbac = dict(VIEWER)
    rbac["deny_tools"] = ["search_invoices"]
    engine = _engine(_project(rbac), monkeypatch)
    ctx = CallContext(request_id="t", claims={"roles": ["admin"]})
    with pytest.raises(AuthError, match="is denied"):
        await dispatch(
            engine,
            "search_invoices",
            {},
            ctx=ctx,
            enable_define=False,
            drafts_path=tmp_path / "tools.drafts.yaml",
        )


@pytest.mark.asyncio
async def test_run_tool_denied_inner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(_project(), monkeypatch)
    ctx = CallContext(request_id="t", claims={"roles": ["viewer"]})
    with pytest.raises(AuthError, match="not permitted"):
        await dispatch(
            engine,
            "run_tool",
            {"name": "count_invoices", "arguments": {}},
            ctx=ctx,
            enable_define=False,
            drafts_path=tmp_path / "tools.drafts.yaml",
        )
