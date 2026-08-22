"""Load one or more TDS files and route tool catalogs by JWT claim."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.observe.metrics import configure_metrics
from vectorsmith_core.observe.tracing import configure_tracing


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

    async def embed_health(self) -> tuple[bool, str | None]:
        return await self.engines[self.default].embed_health()


def project_name(path: Path) -> str:
    return path.stem


def load_engines(
    paths: list[Path],
    *,
    env: dict[str, str] | None,
    credential_resolver: Any | None = None,
    embed_provider: Any | None = None,
    audit_sink: Any | None = None,
) -> dict[str, Engine]:
    engines: dict[str, Engine] = {}
    owners: dict[str, str] = {}
    resolver = credential_resolver or EnvCredentialResolver(env or {})
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
        engines[name] = Engine(
            project,
            credential_resolver=resolver,
            embed_provider=embed_provider,
            audit_sink=audit_sink,
        )
    return engines


def configure_observability(engine: Engine) -> None:
    obs = engine.project.tds.observability
    configure_tracing(obs.tracing.enabled, service_name=obs.tracing.service_name)
    configure_metrics(obs.metrics.enabled)
