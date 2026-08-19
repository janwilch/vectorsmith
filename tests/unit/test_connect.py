"""connect() compiles YAML without a framework extra."""

from __future__ import annotations

import asyncio
from pathlib import Path

from vectorsmith import connect


def _invoice_yaml(tmp_path: Path) -> Path:
    yaml = tmp_path / "tools.yaml"
    yaml.write_text(
        """
tds_version: "1"
connections:
  invoices:
    backend: qdrant
    url: http://localhost:6333
tools:
  - name: search_invoices
    description: Search invoices by client status and due date for billing.
    target: { connection: invoices, collection: invoices }
"""
    )
    return yaml


def test_connect_names_and_anthropic(tmp_path: Path) -> None:
    vs = connect(_invoice_yaml(tmp_path), env={"QDRANT_URL": "http://localhost:6333"})
    try:
        assert "search_invoices" in vs.names
        anth = vs.as_anthropic()
        search = next(t for t in anth if t["name"] == "search_invoices")
        assert search["description"]
        assert search["input_schema"]["type"] == "object"
        assert search["input_schema"]["properties"]
    finally:
        asyncio.run(vs.aclose())


def test_connect_unknown_tool(tmp_path: Path) -> None:
    vs = connect(_invoice_yaml(tmp_path), env={"QDRANT_URL": "http://localhost:6333"})
    try:

        async def _go() -> None:
            try:
                await vs.call("not_a_tool", {})
            except KeyError as exc:
                assert "not_a_tool" in str(exc)
            else:
                raise AssertionError("expected KeyError")

        asyncio.run(_go())
    finally:
        asyncio.run(vs.aclose())


def test_openai_agents_import_error_without_sdk(tmp_path: Path, monkeypatch) -> None:
    vs = connect(_invoice_yaml(tmp_path), env={"QDRANT_URL": "http://localhost:6333"})
    try:
        import sys
        import types

        # Force the adapter's import to fail even if openai-agents is installed.
        monkeypatch.setitem(sys.modules, "agents", types.ModuleType("agents"))
        try:
            vs.as_openai_agents()
        except ImportError as exc:
            assert "vectorsmith[openai-agents]" in str(exc)
        else:
            raise AssertionError("expected ImportError")
    finally:
        asyncio.run(vs.aclose())
