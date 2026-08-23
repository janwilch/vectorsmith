"""Vault / aws_sm / k8s resolve, OPA validate, cross_encoder, multi-project embed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from vectorsmith_cli.http.app import build_app
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_cli.serve_router import ProjectRouter, load_engines
from vectorsmith_cli.validate_cmd import run_validate
from vectorsmith_core.execute.rerank import clear_cross_encoder_cache, resolve_rerank_provider
from vectorsmith_core.security.credentials import build_credential_resolver
from vectorsmith_core.tds.models import AwsSmSpec, K8sSpec, QdrantConn, VaultCredSpec


@pytest.mark.asyncio
async def test_vault_aws_k8s_resolution() -> None:
    async def vault(_spec: VaultCredSpec) -> dict[str, str]:
        return {"url": "http://from-vault"}

    async def aws(spec: AwsSmSpec) -> dict[str, str]:
        assert spec.secret_id == "prod/q"  # noqa: S105
        return {"url": "http://from-sm"}

    async def k8s(spec: K8sSpec) -> dict[str, str]:
        assert spec.secret == "qdrant"  # noqa: S105
        return {"url": "http://from-k8s"}

    resolver = build_credential_resolver(
        {}, vault_fetch=vault, aws_fetch=aws, k8s_fetch=k8s
    )
    vault_spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "vault", "vault": {"path": "secret/data/q"}},  # type: ignore[arg-type]
    )
    aws_spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "aws_sm", "aws_sm": {"secret_id": "prod/q"}},  # type: ignore[arg-type]
    )
    k8s_spec = QdrantConn(
        backend="qdrant",
        url="${QDRANT_URL}",
        credentials={"provider": "k8s", "k8s": {"secret": "qdrant"}},  # type: ignore[arg-type]
    )
    assert (await resolver.resolve("v", vault_spec)).values["url"] == "http://from-vault"
    assert (await resolver.resolve("a", aws_spec)).values["url"] == "http://from-sm"
    assert (await resolver.resolve("k", k8s_spec)).values["url"] == "http://from-k8s"


def test_validate_policy_runs_opa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    policy = tmp_path / "custom.rego"
    policy.write_text("package vectorsmith.custom\n")

    class Proc:
        returncode = 0
        stdout = '{"result":[{"expressions":[{"value":{"deny":["no public bind"]}}]}]}'
        stderr = ""

    monkeypatch.setattr(
        "vectorsmith_core.policy.eval_policy.shutil.which", lambda _n: "/usr/bin/opa"
    )
    monkeypatch.setattr(
        "vectorsmith_core.policy.eval_policy.subprocess.run",
        lambda *_a, **_k: Proc(),
    )
    code = run_validate(path, policy=policy)
    assert code == 2


@pytest.mark.asyncio
async def test_cross_encoder_rerank_orders_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEnc:
        def __init__(self, model: str) -> None:
            self.model = model

        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            return [0.1, 0.9]

    import sys
    import types

    mod = types.ModuleType("sentence_transformers")
    mod.CrossEncoder = FakeEnc  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", mod)
    clear_cross_encoder_cache()
    ranked = await resolve_rerank_provider("cross_encoder").rerank(
        "q",
        [{"title": "low"}, {"title": "high"}],
        spec=type("S", (), {"model": "ce", "config": {}})(),
    )
    assert [r["title"] for r in ranked] == ["high", "low"]
    clear_cross_encoder_cache()


def _lookup_yaml(path: Path, tool: str) -> None:
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
                "    kind: lookup",
                "    target: {connection: main, collection: invoices}",
            ]
        )
        + "\n"
    )


def _search_yaml(path: Path, tool: str) -> None:
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
                "    query: {param: query}",
            ]
        )
        + "\n"
    )


def test_multi_project_readyz_checks_routed_embed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = tmp_path / "internal.yaml"
    routed = tmp_path / "external.yaml"
    _lookup_yaml(default, "lookup_internal")
    _search_yaml(routed, "search_external")
    engines = load_engines([default, routed], env={})
    called: list[str] = []

    async def ok_health() -> tuple[bool, str | None]:
        called.append("ok")
        return True, "fastembed"

    async def bad_health() -> tuple[bool, str | None]:
        called.append("bad")
        return False, "fastembed"

    engines["internal"].embed_health = ok_health  # type: ignore[method-assign]
    engines["external"].embed_health = bad_health  # type: ignore[method-assign]
    router = ProjectRouter(engines, route_claim="product", default="internal")
    default_engine = engines["internal"]

    async def up(*_a: Any, **_k: Any) -> dict[str, Any]:
        from vectorsmith_core.api import HealthStatus

        return {"main": HealthStatus(ok=True, detail="ok", latency_ms=1)}

    monkeypatch.setattr(router, "health", up)
    monkeypatch.setattr(default_engine, "health", up)
    app = build_app(
        engine=default_engine,
        enable_define=False,
        auth="none",
        public_url="https://example.test",
        store=AuthStore(tmp_path / "auth.db"),
        drafts_path=tmp_path / "d.yaml",
        router=router,
    )
    res = TestClient(app).get("/readyz")
    assert res.status_code == 503
    assert res.json()["embed"]["ok"] is False
    assert "external" in (res.json()["embed"].get("provider") or "")
    assert "bad" in called
