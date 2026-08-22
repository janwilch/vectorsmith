"""Parameter directory / fuzzy resolvers."""

from __future__ import annotations

from typing import Any

import pytest

from vectorsmith_core.adapters.base import RowBatch
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.execute.resolve import clear_directory_cache, seed_directory_cache


def _src(*, backend: str = "qdrant", extra_param: dict[str, Any] | None = None) -> dict[str, Any]:
    conn: dict[str, Any] = {"backend": backend}
    if backend == "qdrant":
        conn["url"] = "http://localhost:6333"
    elif backend == "pinecone":
        conn["api_key"] = "x"
        conn["host"] = "https://idx.svc.pinecone.io"
    param = extra_param or {
        "name": "client",
        "path": "client_name",
        "dtype": "keyword",
        "op": "eq",
        "enum": ["Acme Corp", "Globex"],
        "resolve": {
            "kind": "directory",
            "connection": "main",
            "collection": "invoices",
            "field": "client_name",
            "min_confidence": 0.72,
            "cache_ttl_s": 600,
        },
    }
    return {
        "tds_version": "1",
        "connections": {"main": conn},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "parameters": [param],
            }
        ],
    }


def _engine(src: dict[str, Any], monkeypatch: pytest.MonkeyPatch, *, sample_rows=None):
    env = {"QDRANT_URL": "http://localhost:6333"} if "qdrant" in str(src) else {}
    project = load_project(src, env=env)
    engine = Engine(project, credential_resolver=EnvCredentialResolver({}))
    sampled = list(sample_rows or [])

    class Fake:
        def __init__(self) -> None:
            self.sampled = 0
            self.filter_ir = None

        def compile_filter(self, node: object) -> object:
            return node

        async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
            _ = collection, n
            self.sampled += 1
            return sampled

        async def search(self, req: Any) -> RowBatch:
            self.filter_ir = req.filter_ir
            return RowBatch(rows=[{"ok": True}], exhausted=True)

    fake = Fake()

    async def _adapter(_name: str) -> Fake:
        return fake

    monkeypatch.setattr(engine, "_adapter", _adapter)
    return engine, fake


def test_vb4021_directory_on_pinecone() -> None:
    project = load_project(_src(backend="pinecone"), env={})
    assert any(i.code == "VB4021" for i in project.issues)


@pytest.mark.asyncio
async def test_exact_match_skips_scroll(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_directory_cache()
    engine, fake = _engine(_src(), monkeypatch, sample_rows=[{"client_name": "Acme Corp"}])
    out = await engine.call(
        "search_invoices",
        {"client": "Acme Corp"},
        ctx=CallContext(request_id="t"),
    )
    assert out.count == 1
    assert fake.sampled == 0


@pytest.mark.asyncio
async def test_fuzzy_resolves_typo(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_directory_cache()
    seed_directory_cache("main", "invoices", "client_name", ["Acme Corp", "Globex"])
    engine, fake = _engine(_src(), monkeypatch, sample_rows=[])
    await engine.call(
        "search_invoices",
        {"client": "acme cor"},
        ctx=CallContext(request_id="t"),
    )
    assert fake.sampled == 0
    node = fake.filter_ir
    blob = str(node)
    assert "Acme Corp" in blob


@pytest.mark.asyncio
async def test_unresolved_returns_alternatives(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_directory_cache()
    seed_directory_cache("main", "invoices", "client_name", ["Acme Corp", "Globex"])
    engine, _fake = _engine(_src(), monkeypatch)
    out = await engine.call(
        "search_invoices",
        {"client": "zzzz-unknown"},
        ctx=CallContext(request_id="t"),
    )
    assert out.count == 0
    assert "VB4020" in out.warnings
    assert out.message and "Did you mean" in out.message
    assert "Acme Corp" in out.message or "Globex" in out.message


@pytest.mark.asyncio
async def test_directory_cache_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_directory_cache()
    engine, fake = _engine(
        _src(),
        monkeypatch,
        sample_rows=[{"client_name": "Acme Corp"}],
    )
    await engine.call(
        "search_invoices", {"client": "acme cor"}, ctx=CallContext(request_id="t")
    )
    first = fake.sampled
    await engine.call(
        "search_invoices", {"client": "acme cor"}, ctx=CallContext(request_id="t")
    )
    assert fake.sampled == first
