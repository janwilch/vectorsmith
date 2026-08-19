"""Draft inertness, injection, cap, expiry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from vectorsmith_cli.serve_common import _define_tool, expire_old_drafts
from vectorsmith_core.api import draft_tool, load_project


def _project():
    return load_project(
        {
            "tds_version": "1",
            "connections": {
                "main": {
                    "backend": "qdrant",
                    "url": "http://localhost:6333",
                    "builtin_defaults": {
                        "static_filters": [{"path": "tenant", "op": "eq", "value": "acme"}]
                    },
                }
            },
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                }
            ],
        }
    )


def test_pending_draft_not_in_project() -> None:
    project = _project()
    before = set(project.tools)
    draft_tool(
        project,
        {},
        {
            "name": "search_by_amount",
            "description": "Find invoices above an amount for collections work now.",
            "kind": "search",
            "target": {"connection": "main", "collection": "invoices"},
            "parameters": [{"name": "min_amount", "path": "amount", "dtype": "float", "op": "gte"}],
        },
    )
    assert set(project.tools) == before


def test_static_filter_injection() -> None:
    project = _project()
    draft = draft_tool(
        project,
        {},
        {
            "name": "search_by_amount",
            "description": "Find invoices above an amount for collections work now.",
            "kind": "search",
            "target": {"connection": "main", "collection": "invoices"},
        },
    )
    assert any(s.path == "tenant" for s in draft.spec.static_filters)


def test_cap_ten_pending(tmp_path: Path) -> None:
    project = _project()
    path = tmp_path / "tools.drafts.yaml"
    lines = ["drafts:"]
    for i in range(10):
        lines.append("- status: pending")
        lines.append(f"  tool: {{name: d{i}}}")
    path.write_text("\n".join(lines) + "\n")
    out = _define_tool(
        project,
        {
            "name": "search_extra_one",
            "description": "Another search tool for invoices by due date today.",
            "spec": {
                "name": "search_extra_one",
                "description": "Another search tool for invoices by due date today.",
                "target": {"connection": "main", "collection": "invoices"},
            },
        },
        path,
    )
    assert "cap" in out["message"].lower()


def test_expiry(tmp_path: Path) -> None:
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    path = tmp_path / "tools.drafts.yaml"
    path.write_text(
        "drafts:\n"
        f"- status: pending\n  created_at: '{old}'\n  tool: {{name: stale}}\n"
    )
    expire_old_drafts(path)
    assert "expired" in path.read_text()
