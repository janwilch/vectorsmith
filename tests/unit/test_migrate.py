"""TDS migrate v1 → v2."""

from __future__ import annotations

from pathlib import Path

import pytest

from vectorsmith_cli.migrate_cmd import run_migrate
from vectorsmith_core.api import load_project
from vectorsmith_core.tds.migrate import migrate_document


def test_v1_still_loads_with_deprecation() -> None:
    project = load_project(
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
    assert project.tds.tds_version == "1"
    assert any(i.code == "VB0002" for i in project.issues)


def test_migrate_rewrites_static_filters_list() -> None:
    out = migrate_document(
        {
            "tds_version": "1",
            "tools": [
                {
                    "name": "search_invoices",
                    "static_filters": [{"path": "tenant", "op": "eq", "value": "acme"}],
                }
            ],
        },
        from_version="1",
        to_version="2",
    )
    assert out["tds_version"] == "2"
    assert out["tools"][0]["static_filters"] == {
        "must": [{"path": "tenant", "op": "eq", "value": "acme"}]
    }


def test_dry_run_prints_diff_without_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "tools.yaml"
    path.write_text('tds_version: "1"\nconnections: {}\n')
    before = path.read_text()
    code = run_migrate(path, from_version="1", to_version="2", dry_run=True, write=False)
    assert code == 0
    assert path.read_text() == before
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "tds_version" in captured.out


def test_write_updates_file(tmp_path: Path) -> None:
    path = tmp_path / "tools.yaml"
    path.write_text('tds_version: "1"\nconnections: {}\n')
    code = run_migrate(path, from_version="1", to_version="2", dry_run=False, write=True)
    assert code == 0
    text = path.read_text()
    assert "tds_version" in text and "2" in text
