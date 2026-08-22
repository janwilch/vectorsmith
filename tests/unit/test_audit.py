"""observability.audit events from dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vectorsmith_cli.observe.sinks import FileSink
from vectorsmith_cli.serve_common import dispatch
from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.observe.audit import redact_args

_REDACTED = "[REDACTED]"


class _Rec:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def flush(self) -> None:
        return None


def _src() -> dict[str, Any]:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "observability": {"audit": {"enabled": True}},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
            }
        ],
    }


def _engine(monkeypatch: pytest.MonkeyPatch, sink: _Rec) -> Engine:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    engine = Engine(
        project, credential_resolver=EnvCredentialResolver({}), audit_sink=sink
    )

    class Fake:
        def compile_filter(self, node: object) -> object:
            return node

        async def search(self, req: Any) -> RowBatch:
            _ = req
            return RowBatch(rows=[{"id": "1"}], exhausted=True)

    async def _adapter(_name: str) -> Fake:
        return Fake()

    monkeypatch.setattr(engine, "_adapter", _adapter)
    return engine


@pytest.mark.asyncio
async def test_success_emits_one_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = _Rec()
    engine = _engine(monkeypatch, sink)
    await dispatch(
        engine,
        "search_invoices",
        {"query": "x", "token": "secret-value"},
        ctx=CallContext(request_id="req-1", principal="alice"),
        enable_define=False,
        drafts_path=tmp_path / "d.yaml",
    )
    assert len(sink.events) == 1
    ev = sink.events[0]
    assert ev["audit_version"] == "1"
    assert ev["status"] == "ok"
    assert ev["tool"] == "search_invoices"
    assert ev["principal"] == "alice"
    assert ev["request_id"] == "req-1"
    assert ev["result_count"] == 1
    assert ev["args"]["token"] == _REDACTED
    assert ev["args"]["query"] == "x"


@pytest.mark.asyncio
async def test_failure_emits_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sink = _Rec()
    engine = _engine(monkeypatch, sink)
    with pytest.raises(InvalidArgumentsError):
        await dispatch(
            engine,
            "no_such_tool",
            {},
            ctx=CallContext(request_id="req-2"),
            enable_define=False,
            drafts_path=tmp_path / "d.yaml",
        )
    assert len(sink.events) == 1
    assert sink.events[0]["status"] == "error"
    assert sink.events[0]["error_code"] == "invalid_arguments"


def test_redact_args() -> None:
    out = redact_args({"query": "q", "password": "p", "Token": "t"}, ["password", "token"])
    assert out["query"] == "q"
    assert out["password"] == _REDACTED
    assert out["Token"] == _REDACTED


@pytest.mark.asyncio
async def test_emit_failure_does_not_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Boom(_Rec):
        async def emit(self, event: dict[str, Any]) -> None:
            raise RuntimeError("sink down")

    engine = _engine(monkeypatch, Boom())
    out = await dispatch(
        engine,
        "search_invoices",
        {},
        ctx=CallContext(request_id="req-3"),
        enable_define=False,
        drafts_path=tmp_path / "d.yaml",
    )
    assert out["count"] == 1


def test_file_sink_mode_0600(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    FileSink(path)
    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600
