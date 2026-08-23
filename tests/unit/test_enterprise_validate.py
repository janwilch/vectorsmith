"""Dedicated VE001–VE007 coverage for validate --enterprise."""

from __future__ import annotations

from typing import Any

from vectorsmith_core.api import load_project
from vectorsmith_core.compilepkg.enterprise import enterprise_issues
from vectorsmith_core.tds.loader import read_source


def _project(src: dict[str, Any]):
    return load_project(src, env={"QDRANT_URL": "http://localhost:6333"})


def _tool(**extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": "search_invoices",
        "description": "Search invoices by client status and due date for billing.",
        "target": {"connection": "main", "collection": "invoices"},
    }
    row.update(extra)
    return row


def test_ve001_authoring() -> None:
    project = _project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "${QDRANT_URL}"}},
            "authoring": {"define_tool": True},
            "security": {"tenancy": {"mode": "claim", "claim": "tenant_id"}},
            "tools": [_tool()],
        }
    )
    issues = enterprise_issues(project.tds)
    assert any(i.code == "VE001" for i in issues)


def test_ve002_requires_tenancy_or_must() -> None:
    project = _project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "${QDRANT_URL}"}},
            "security": {"tenancy": {"mode": "none"}},
            "tools": [_tool()],
        }
    )
    issues = enterprise_issues(project.tds)
    assert any(i.code == "VE002" for i in issues)


def test_ve003_limit_max() -> None:
    project = _project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "${QDRANT_URL}"}},
            "security": {"tenancy": {"mode": "claim", "claim": "t"}},
            "tools": [_tool(output={"limit_max": 200})],
        }
    )
    issues = enterprise_issues(project.tds)
    assert any(i.code == "VE003" for i in issues)


def test_ve004_literal_url(tmp_path: Any) -> None:
    path = tmp_path / "tools.yaml"
    path.write_text(
        "\n".join(
            [
                'tds_version: "1"',
                "connections:",
                "  main:",
                "    backend: qdrant",
                "    url: http://localhost:6333",
                "tools:",
                "  - name: search_invoices",
                "    description: Search invoices by client status and due date for billing.",
                "    target: {connection: main, collection: invoices}",
            ]
        )
        + "\n"
    )
    project = load_project(path, env={})
    raw = read_source(path)
    issues = enterprise_issues(project.tds, raw=raw if isinstance(raw, dict) else None)
    assert any(i.code == "VE004" for i in issues)


def test_ve005_meta_tools_warning() -> None:
    project = _project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "${QDRANT_URL}"}},
            "security": {"tenancy": {"mode": "claim", "claim": "t"}},
            "tools": [_tool()],
        }
    )
    issues = enterprise_issues(project.tds, meta_tools_enabled=True)
    warn = [i for i in issues if i.code == "VE005"]
    assert warn and warn[0].severity == "warning"


def test_ve007_fastembed_warning() -> None:
    project = _project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "${QDRANT_URL}"}},
            "security": {"tenancy": {"mode": "claim", "claim": "t"}},
            "tools": [_tool()],
        }
    )
    issues = enterprise_issues(project.tds)
    warn = [i for i in issues if i.code == "VE007"]
    assert warn and warn[0].severity == "warning"
