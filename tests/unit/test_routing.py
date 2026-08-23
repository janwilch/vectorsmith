"""Multi-project routing by claim."""

from __future__ import annotations

from pathlib import Path

import pytest

from vectorsmith_cli.serve_router import ProjectRouter, load_engines, project_name
from vectorsmith_core.api import CallContext, EnvCredentialResolver, Project
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine


def _write(path: Path, name: str, tool: str) -> None:
    path.write_text(
        "\n".join(
            [
                'tds_version: "1"',
                "connections:",
                "  main:",
                "    backend: qdrant",
                "    url: http://localhost:6333",
                "tools:",
                f"  - name: {tool}",
                "    description: Search invoices by client status and due date for billing.",
                "    target: {connection: main, collection: invoices}",
            ]
        )
        + "\n"
    )


def test_single_project_name_is_stem(tmp_path: Path) -> None:
    p = tmp_path / "internal.yaml"
    _write(p, "internal", "search_internal")
    assert project_name(p) == "internal"


def test_route_by_claim_selects_catalog(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    b = tmp_path / "external.yaml"
    _write(a, "internal", "search_internal")
    _write(b, "external", "search_external")
    engines = load_engines(
        [a, b],
        env={},
        credential_resolver=EnvCredentialResolver({}),
    )
    router = ProjectRouter(engines, route_claim="product", default="internal")
    internal = router.resolve(CallContext(request_id="1", claims={"product": "internal"}))
    external = router.resolve(CallContext(request_id="2", claims={"product": "external"}))
    assert "search_internal" in internal.project.tools
    assert "search_external" in external.project.tools
    assert "search_external" not in internal.project.tools


def test_cross_project_tool_rejected(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    b = tmp_path / "external.yaml"
    _write(a, "internal", "search_internal")
    _write(b, "external", "search_external")
    engines = load_engines([a, b], env={}, credential_resolver=EnvCredentialResolver({}))
    router = ProjectRouter(engines, route_claim="product", default="internal")
    ctx = CallContext(request_id="1", claims={"product": "internal"})
    with pytest.raises(InvalidArgumentsError):
        router.resolve_for_tool(ctx, "search_external")


def test_tool_name_collision_exits(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    b = tmp_path / "external.yaml"
    _write(a, "internal", "search_docs")
    _write(b, "external", "search_docs")
    with pytest.raises(SystemExit) as exc:
        load_engines([a, b], env={}, credential_resolver=EnvCredentialResolver({}))
    assert exc.value.code == 2


def test_per_project_audit_sink(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    b = tmp_path / "external.yaml"
    _write(a, "internal", "search_internal")
    _write(b, "external", "search_external")
    sinks: dict[str, str] = {}

    def make_sink(project: Project) -> str:
        name = next(iter(project.tools))
        sinks[name] = f"sink-{name}"
        return sinks[name]

    engines = load_engines([a, b], env={}, make_audit_sink=make_sink)
    assert engines["internal"].audit_sink == "sink-search_internal"
    assert engines["external"].audit_sink == "sink-search_external"


def test_router_default_engine_is_engine(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    _write(a, "internal", "search_internal")
    engines = load_engines([a], env={}, credential_resolver=EnvCredentialResolver({}))
    router = ProjectRouter(engines, route_claim=None, default="internal")
    assert isinstance(router.resolve(CallContext(request_id="1")), Engine)
