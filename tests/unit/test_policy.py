"""Custom --policy runs opa eval; builtin packs stay in-process."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vectorsmith_core.api import load_project
from vectorsmith_core.policy.eval_policy import eval_policies


def _tds():
    return load_project(
        {
            "tds_version": "1",
            "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
            "tools": [
                {
                    "name": "search_invoices",
                    "description": "Search invoices by client status and due date for billing.",
                    "target": {"connection": "main", "collection": "invoices"},
                    "output": {"fields": ["pan", "title"]},
                }
            ],
        },
        env={"QDRANT_URL": "http://localhost:6333"},
    ).tds


def test_builtin_pci() -> None:
    issues = eval_policies(_tds(), builtin="pci")
    assert any("pan" in i.message for i in issues)


def test_opa_missing(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr("vectorsmith_core.policy.eval_policy.shutil.which", lambda _n: None)
    issues = eval_policies(_tds(), policy_path=tmp_path / "custom.rego")
    assert issues[0].code == "POL000"
    assert "not installed" in issues[0].message


def test_opa_eval_denies(monkeypatch: Any, tmp_path: Path) -> None:
    policy = tmp_path / "custom.rego"
    policy.write_text("package vectorsmith.custom\n")

    class Proc:
        returncode = 0
        stdout = json.dumps(
            {"result": [{"expressions": [{"value": {"deny": ["no public bind"]}}]}]}
        )
        stderr = ""

    monkeypatch.setattr(
        "vectorsmith_core.policy.eval_policy.shutil.which", lambda _n: "/usr/bin/opa"
    )
    monkeypatch.setattr(
        "vectorsmith_core.policy.eval_policy.subprocess.run",
        lambda *_a, **_k: Proc(),
    )
    issues = eval_policies(_tds(), policy_path=policy)
    assert [i.code for i in issues] == ["POL001"]
    assert issues[0].message == "no public bind"
