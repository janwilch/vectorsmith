"""Authoring façade.

``load_project`` reads a TDS, interpolates env, synthesizes built-ins, validates,
and compiles. Drafts are never read during Project assembly.

Execution (``Engine.call``) is internal to the CLI MCP server. Agents must
attach ``vectorsmith serve``, not import an executor.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from vectorsmith_core.compilepkg.builtins import synthesize
from vectorsmith_core.compilepkg.compiler import ExecutionPlan, compile_tool
from vectorsmith_core.compilepkg.drafts import draft_tool as _draft_tool
from vectorsmith_core.compilepkg.drafts import promote_draft
from vectorsmith_core.compilepkg.validator import validate
from vectorsmith_core.errors import MissingEnvError
from vectorsmith_core.tds.loader import parse_tds
from vectorsmith_core.tds.models import TDSFile, ToolSpec


class Issue(BaseModel):
    """A collected validation finding with a stable ``VBxxxx`` code."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    tool: str | None = None
    path: str | None = None
    line: int | None = None


class CompiledTool(BaseModel):
    """A compiled tool ready for MCP ``tools/list``."""

    name: str
    mcp_schema: dict[str, Any]
    is_synthetic: bool = False
    model_config = ConfigDict(arbitrary_types_allowed=True)
    plan: ExecutionPlan | None = Field(default=None, exclude=True)


class Project:
    """An assembled, compiled TDS. Does not read draft stores."""

    def __init__(
        self,
        tds: TDSFile,
        issues: list[Issue],
        tools: dict[str, CompiledTool],
    ) -> None:
        self.tds = tds
        self.issues = issues
        self.tools = tools

    def mcp_tool_schemas(self) -> list[dict[str, Any]]:
        """Compiled MCP schemas ``serve`` advertises (user tools, then built-ins).

        For inspection and the MCP server. Do not bind these to an LLM SDK;
        attach ``vectorsmith serve`` as an MCP client instead.
        """
        user = [t.mcp_schema for t in self.tools.values() if not t.is_synthetic]
        built = [t.mcp_schema for t in self.tools.values() if t.is_synthetic]
        return user + built


class ToolDraft(BaseModel):
    spec: ToolSpec
    validator_issues: list[Issue]
    provenance: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"


def draft_tool(project: Project, provenance: dict[str, Any], proposed: dict[str, Any]) -> ToolDraft:
    """Validate a proposed tool. Never mutates ``project``."""
    return _draft_tool(project, provenance, proposed)


class ResolvedCredentials(BaseModel):
    values: dict[str, str]
    model_config = ConfigDict(frozen=True)

    def __repr__(self) -> str:
        return "<ResolvedCredentials ****>"


class CredentialResolver(Protocol):
    async def resolve(self, name: str, spec: object) -> ResolvedCredentials: ...


class EnvCredentialResolver:
    """Resolve connection secrets from the environment. All-missing-at-once."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = dict(env) if env is not None else dict(os.environ)

    async def resolve(self, name: str, spec: object) -> ResolvedCredentials:
        needed: list[str] = []
        values: dict[str, str] = {}
        raw = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)  # type: ignore[arg-type]
        for key, val in raw.items():
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                inner = val[2:-1]
                var = inner.split(":-", 1)[0]
                if var in self._env:
                    values[key] = self._env[var]
                elif ":-" in inner:
                    values[key] = inner.split(":-", 1)[1]
                else:
                    needed.append(var)
            elif isinstance(val, str):
                values[key] = val
        if needed:
            raise MissingEnvError(needed)
        return ResolvedCredentials(values=values)


class EmbedProvider(Protocol):
    async def embed(self, texts: list[str], model: str) -> list[list[float]]: ...

    def dims(self, model: str) -> int: ...


class CallContext(BaseModel):
    request_id: str
    deadline_s: float = 25.0


class ToolResult(BaseModel):
    rows: list[dict[str, Any]]
    count: int
    truncated: bool = False
    may_be_incomplete: bool = False
    exact_search: bool = False
    search_mode: Literal["dense", "hybrid", "none"] = "none"
    warnings: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    compiled_query: dict[str, Any] | None = None


class HealthStatus(BaseModel):
    ok: bool
    detail: str = ""


def load_project(
    source: str | Path | dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    strict: bool = False,
) -> Project:
    """Read → env interpolation → pydantic → built-in synthesis → validate → compile.

    Draft stores are never consulted.
    """
    tds, vb1003, extras, secrets = parse_tds(source, env=env)
    issues: list[Issue] = []
    for path in vb1003:
        issues.append(
            Issue(
                severity="error",
                code="VB1003",
                message="environment interpolation is only allowed under connections",
                path=path,
            )
        )
    for path, key in extras:
        issues.append(
            Issue(
                severity="warning",
                code="VB0001",
                message=f"unknown key '{key}'",
                path=path or key,
            )
        )
    for path in secrets:
        issues.append(
            Issue(
                severity="error",
                code="VB1003",
                message="inline secret detected — use ${VAR} under connections",
                path=path,
            )
        )
    tds = synthesize(tds)
    issues.extend(validate(tds))
    tools: dict[str, CompiledTool] = {}
    for spec in tds.tools:
        schema, plan = compile_tool(spec)
        tools[spec.name] = CompiledTool(
            name=spec.name,
            mcp_schema=schema,
            is_synthetic=spec._synthetic,
            plan=plan,
        )
    if strict and any(i.severity == "warning" for i in issues):
        pass  # caller (CLI) maps warnings to exit 1
    return Project(tds=tds, issues=issues, tools=tools)


__all__ = [
    "Issue",
    "Project",
    "ToolDraft",
    "draft_tool",
    "load_project",
    "promote_draft",
]
