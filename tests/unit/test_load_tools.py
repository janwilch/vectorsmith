"""load_tools compiles YAML into LangChain tools (no MCP subprocess)."""

from __future__ import annotations

from pathlib import Path

from vectorsmith import load_tools


def test_load_tools_names(tmp_path: Path) -> None:
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
    tools = load_tools(yaml, env={"QDRANT_URL": "http://localhost:6333"})
    try:
        names = [t.name for t in tools]
        assert "search_invoices" in names
        search = next(t for t in tools if t.name == "search_invoices")
        assert search.description
        assert search.args_schema is not None
    finally:
        import asyncio

        asyncio.run(tools.aclose())
