"""Load one or more TDS files and route tool catalogs by JWT claim."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vectorsmith_core.api import CallContext, load_project
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.observe.metrics import configure_metrics
from vectorsmith_core.observe.tracing import configure_tracing
from vectorsmith_core.security.credentials import build_credential_resolver


class ProjectRouter:
    def __init__(
        self,
        engines: dict[str, Engine],
        *,
        route_claim: str | None,
        default: str,
    ) -> None:
        if default not in engines:
            raise InvalidArgumentsError(detail=f"unknown default project '{default}'")
        self.engines = engines
        self.route_claim = route_claim
        self.default = default

    @property
    def project(self) -> Any:
        return self.engines[self.default].project

    def resolve(self, ctx: CallContext | None) -> Engine:
        name = self.default
        if self.route_claim and ctx is not None:
            claimed = (ctx.claims or {}).get(self.route_claim)
            if claimed:
                name = str(claimed)
        engine = self.engines.get(name)
        if engine is None:
            raise InvalidArgumentsError(detail=f"unknown project '{name}'")
        return engine

    def resolve_for_tool(self, ctx: CallContext | None, tool: str) -> Engine:
        engine = self.resolve(ctx)
        if tool not in engine.project.tools:
            raise InvalidArgumentsError(
                detail=f"tool '{tool}' is not available in this project"
            )
        return engine

    async def health(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for name, engine in self.engines.items():
            part = await engine.health()
            for key, status in part.items():
                merged[f"{name}.{key}"] = status
        return merged

    async def embed_health(self, *, live_embed: bool = False) -> tuple[bool, str | None]:
        last_provider: str | None = None
        checked = False
        for name, engine in self.engines.items():
            if not project_needs_embed(engine, live_embed=live_embed):
                continue
            checked = True
            ok, provider = await engine.embed_health()
            last_provider = f"{name}:{provider}" if provider else name
            if not ok:
                return False, last_provider
        if not checked:
            return True, None
        return True, last_provider


def project_needs_embed(engine: Engine, *, live_embed: bool = False) -> bool:
    if live_embed:
        return True
    return any(
        t.plan is not None and t.plan.kind in {"search", "pipeline"}
        for t in engine.project.tools.values()
    )


def project_name(path: Path) -> str:
    return path.stem


def load_engines(
    paths: list[Path],
    *,
    env: dict[str, str] | None,
    credential_resolver: Any | None = None,
    embed_provider: Any | None = None,
    audit_sink: Any | None = None,
    make_audit_sink: Callable[[Any], Any] | None = None,
) -> dict[str, Engine]:
    engines: dict[str, Engine] = {}
    owners: dict[str, str] = {}
    resolver = credential_resolver or build_credential_resolver(env)
    for path in paths:
        name = project_name(path)
        if name in engines:
            print(f"duplicate project name '{name}'", file=sys.stderr)
            raise SystemExit(2)
        project = load_project(path, env=env)
        errors = [i for i in project.issues if i.severity == "error"]
        if errors:
            for issue in errors:
                print(f"{issue.code}: {issue.message}", file=sys.stderr)
            raise SystemExit(2)
        for tool in project.tools:
            if tool in owners:
                print(
                    f"tool '{tool}' is defined in both '{owners[tool]}' and '{name}'",
                    file=sys.stderr,
                )
                raise SystemExit(2)
            owners[tool] = name
        sink = make_audit_sink(project) if make_audit_sink is not None else audit_sink
        engines[name] = Engine(
            project,
            credential_resolver=resolver,
            embed_provider=embed_provider,
            audit_sink=sink,
        )
    return engines


def configure_observability(engine: Engine) -> None:
    configure_observability_many([engine])


def configure_observability_many(engines: list[Engine]) -> None:
    """Enable tracing/metrics if any loaded project asks for them."""
    tracing_on = False
    metrics_on = False
    service = "vectorsmith"
    endpoint: str | None = None
    exporter: str | None = None
    for engine in engines:
        obs = engine.project.tds.observability
        if obs.metrics.enabled:
            metrics_on = True
        if obs.tracing.enabled:
            tracing_on = True
            service = obs.tracing.service_name
            endpoint = obs.tracing.endpoint
            exporter = obs.tracing.exporter
    configure_tracing(
        tracing_on,
        service_name=service,
        endpoint=endpoint,
        exporter=exporter,
    )
    configure_metrics(metrics_on)
