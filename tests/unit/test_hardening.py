"""profiles.enterprise hardening at serve time."""

from __future__ import annotations

from typing import Any

from vectorsmith import connect
from vectorsmith_core.api import load_project
from vectorsmith_core.security.hardening import (
    apply_serve_hardening,
    apply_serve_hardening_many,
    hardening_blocks_authoring,
    serve_hardening_errors,
)


def _src(*, profile: bool, tenancy: str = "claim", limit_max: int = 50) -> dict[str, Any]:
    data: dict[str, Any] = {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "security": {"tenancy": {"mode": tenancy, "claim": "tenant_id"}},
        "authoring": {"define_tool": True},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "output": {"limit_max": limit_max},
            }
        ],
    }
    if profile:
        data["profiles"] = {
            "enterprise": {
                "security": {
                    "hardening": {
                        "disable_authoring": True,
                        "disable_meta_tools": True,
                        "require_tenancy": True,
                        "max_limit_max": 100,
                    }
                }
            }
        }
    return data


def test_hardening_overrides_serve_flags() -> None:
    project = load_project(
        _src(profile=True), env={"QDRANT_URL": "http://localhost:6333"}
    )
    enable, meta = apply_serve_hardening(
        project.tds, enable_define=True, include_meta=True
    )
    assert enable is False
    assert meta is False
    assert hardening_blocks_authoring(project.tds) is True


def test_no_profile_leaves_flags() -> None:
    project = load_project(
        _src(profile=False), env={"QDRANT_URL": "http://localhost:6333"}
    )
    enable, meta = apply_serve_hardening(
        project.tds, enable_define=True, include_meta=True
    )
    assert enable is True
    assert meta is True
    assert serve_hardening_errors(project.tds) == []


def test_require_tenancy_refuses_none_without_must() -> None:
    project = load_project(
        _src(profile=True, tenancy="none"),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    errors = serve_hardening_errors(project.tds)
    assert any("require_tenancy" in e for e in errors)


def test_many_files_union_strictest_flags() -> None:
    loose = load_project(
        _src(profile=False), env={"QDRANT_URL": "http://localhost:6333"}
    )
    strict = load_project(
        _src(profile=True), env={"QDRANT_URL": "http://localhost:6333"}
    )
    enable, meta = apply_serve_hardening_many(
        [loose.tds, strict.tds], enable_define=True, include_meta=True
    )
    assert enable is False
    assert meta is False


def test_connect_raises_on_enterprise_hardening() -> None:
    src = _src(profile=True, tenancy="none")
    try:
        connect(src, env={"QDRANT_URL": "http://localhost:6333"})
    except ValueError as exc:
        assert "enterprise hardening" in str(exc)
        return
    raise AssertionError("connect should refuse a broken enterprise profile")


def test_max_limit_max_refuses_oversize() -> None:
    project = load_project(
        _src(profile=True, limit_max=200),
        env={"QDRANT_URL": "http://localhost:6333"},
    )
    errors = serve_hardening_errors(project.tds)
    assert any("max_limit_max" in e for e in errors)
