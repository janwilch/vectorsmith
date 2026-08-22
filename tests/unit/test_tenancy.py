"""Request-scoped security.tenancy (claim / header)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vectorsmith_cli.http.auth.context import call_context_from_request
from vectorsmith_cli.serve_common import dispatch, mcp_schemas
from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import AuthError, InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.ir.filter import And, Cond, IRNode


def _src(*, tenancy: dict[str, Any], params: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "security": {"tenancy": tenancy},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "parameters": params
                or [
                    {
                        "name": "status",
                        "path": "status",
                        "dtype": "keyword",
                        "op": "eq",
                    }
                ],
            }
        ],
    }


def _tenant_eq(node: object, path: str, value: str) -> bool:
    if isinstance(node, Cond):
        return node.path == path and node.op == "eq" and node.value == value
    if isinstance(node, And):
        return any(_tenant_eq(c, path, value) for c in node.children)
    return False


class _FakeAdapter:
    def __init__(self) -> None:
        self.filter_ir: IRNode | None = None

    def compile_filter(self, node: IRNode | None) -> object:
        return node

    async def search(self, req: Any) -> RowBatch:
        self.filter_ir = req.filter_ir  # type: ignore[assignment]
        return RowBatch(rows=[{"tenant_id": "acme", "id": "kept"}], exhausted=True)


async def _engine_with_fake(
    src: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> tuple[Engine, _FakeAdapter]:
    project = load_project(src, env={"QDRANT_URL": "http://localhost:6333"})
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    fake = _FakeAdapter()

    async def _adapter(_name: str) -> _FakeAdapter:
        return fake

    monkeypatch.setattr(engine, "_adapter", _adapter)
    return engine, fake


def test_tenancy_not_in_mcp_schema() -> None:
    project = load_project(
        _src(tenancy={"mode": "claim", "claim": "tenant_id", "path": "tenant_id"}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    blob = str(project.tools["search_invoices"].mcp_schema)
    assert "tenant_id" not in blob
    names = [s["name"] for s in mcp_schemas(project, enable_define=False)]
    assert "search_invoices" in names


def test_vb4011_claim_mode_requires_claim() -> None:
    project = load_project(
        _src(tenancy={"mode": "claim", "path": "tenant_id"}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    assert any(i.code == "VB4011" and i.severity == "error" for i in project.issues)


def test_vb4012_param_path_collision() -> None:
    project = load_project(
        _src(
            tenancy={"mode": "claim", "claim": "tenant_id", "path": "tenant_id"},
            params=[
                {
                    "name": "tenant_id",
                    "path": "tenant_id",
                    "dtype": "keyword",
                    "op": "eq",
                }
            ],
        ),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    assert any(i.code == "VB4012" and i.severity == "warning" for i in project.issues)


@pytest.mark.asyncio
async def test_claim_tenant_filter_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, fake = await _engine_with_fake(
        _src(tenancy={"mode": "claim", "claim": "tenant_id", "path": "tenant_id"}),
        monkeypatch,
    )
    ctx = CallContext(request_id="t", claims={"tenant_id": "acme"})
    await engine.call("search_invoices", {}, ctx=ctx)
    assert _tenant_eq(fake.filter_ir, "tenant_id", "acme")


@pytest.mark.asyncio
async def test_strict_conflict_is_vb4010(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, fake = await _engine_with_fake(
        _src(
            tenancy={
                "mode": "claim",
                "claim": "tenant_id",
                "path": "tenant_id",
                "enforce": "strict",
            },
            params=[
                {
                    "name": "tenant_id",
                    "path": "tenant_id",
                    "dtype": "keyword",
                    "op": "eq",
                }
            ],
        ),
        monkeypatch,
    )
    ctx = CallContext(request_id="t", claims={"tenant_id": "acme"})
    with pytest.raises(InvalidArgumentsError) as exc:
        await engine.call("search_invoices", {"tenant_id": "other"}, ctx=ctx)
    assert exc.value.code == "VB4010"
    assert fake.filter_ir is None


@pytest.mark.asyncio
async def test_run_tool_applies_tenancy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, fake = await _engine_with_fake(
        _src(tenancy={"mode": "claim", "claim": "tenant_id", "path": "tenant_id"}),
        monkeypatch,
    )
    ctx = CallContext(request_id="t", claims={"tenant_id": "acme"})
    await dispatch(
        engine,
        "run_tool",
        {"name": "search_invoices", "arguments": {}},
        ctx=ctx,
        enable_define=False,
        drafts_path=tmp_path / "tools.drafts.yaml",
    )
    assert _tenant_eq(fake.filter_ir, "tenant_id", "acme")


def test_header_bind() -> None:
    project = load_project(
        _src(tenancy={"mode": "header", "header": "X-Tenant-Id", "path": "org"}),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    ctx = call_context_from_request(
        tenancy=project.tds.security.tenancy,
        headers={"X-Tenant-Id": "acme"},
    )
    assert ctx.tenant_value == "acme"
    assert isinstance(ctx.tenant_filter, Cond)
    assert ctx.tenant_filter.path == "org"
    assert ctx.tenant_filter.value == "acme"


@pytest.mark.asyncio
async def test_missing_claim_is_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _fake = await _engine_with_fake(
        _src(tenancy={"mode": "claim", "claim": "tenant_id", "path": "tenant_id"}),
        monkeypatch,
    )
    with pytest.raises(AuthError, match="tenancy value is required"):
        await engine.call("search_invoices", {}, ctx=CallContext(request_id="t"))
