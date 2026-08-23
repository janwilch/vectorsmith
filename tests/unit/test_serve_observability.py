"""Single-project and multi-project HTTP serve wiring (#3, #4)."""

from __future__ import annotations

from pathlib import Path

from vectorsmith_cli.serve_router import configure_observability, load_engines, project_name
from vectorsmith_core.api import load_project
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.security.credentials import build_credential_resolver


def _write(path: Path, tool: str) -> None:
    path.write_text(
        "\n".join(
            [
                'tds_version: "1"',
                "connections:",
                "  main:",
                "    backend: qdrant",
                "    url: http://localhost:6333",
                "security:",
                "  auth:",
                "    mode: jwt",
                "    jwt:",
                "      jwks_url: https://auth.example.com/jwks.json",
                "observability:",
                "  tracing:",
                "    enabled: true",
                "    endpoint: http://collector:4318",
                "    service_name: invoices",
                "tools:",
                f"  - name: {tool}",
                "    description: Search invoices by client status and due date for billing.",
                "    target: {connection: main, collection: invoices}",
            ]
        )
        + "\n"
    )


def test_single_project_configure_observability_uses_endpoint(
    tmp_path: Path, monkeypatch: object
) -> None:
    path = tmp_path / "tools.yaml"
    _write(path, "search_invoices")
    project = load_project(path, env={})
    engine = Engine(project, credential_resolver=build_credential_resolver({}))
    called: dict[str, object] = {}

    def fake_tracing(enabled: bool, **kwargs: object) -> None:
        called["enabled"] = enabled
        called.update(kwargs)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "vectorsmith_cli.serve_router.configure_tracing", fake_tracing
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "vectorsmith_cli.serve_router.configure_metrics", lambda _e: None
    )
    configure_observability(engine)
    assert called["enabled"] is True
    assert called["endpoint"] == "http://collector:4318"
    assert called["service_name"] == "invoices"


def test_multi_project_auth_reads_engine_project(tmp_path: Path) -> None:
    a = tmp_path / "internal.yaml"
    b = tmp_path / "external.yaml"
    _write(a, "search_internal")
    _write(b, "search_external")
    engines = load_engines([a, b], env={})
    default = engines[project_name(a)]
    # This is the field serve_http must use (not a bare `project` name).
    yaml_auth = default.project.tds.security.auth
    assert yaml_auth.jwt.jwks_url == "https://auth.example.com/jwks.json"
