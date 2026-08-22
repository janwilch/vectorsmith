"""Enterprise validation preset (VE00x)."""

from __future__ import annotations

from typing import Any, Literal

from vectorsmith_core.tds.models import TDSFile


def _issue(
    code: str,
    message: str,
    *,
    severity: Literal["error", "warning"] = "error",
    tool: str | None = None,
    path: str | None = None,
) -> Any:
    from vectorsmith_core.api import Issue

    return Issue(severity=severity, code=code, message=message, tool=tool, path=path)


def enterprise_issues(
    tds: TDSFile,
    *,
    raw: dict[str, Any] | None = None,
    meta_tools_enabled: bool = True,
) -> list[Any]:
    issues: list[Any] = []
    if tds.authoring.define_tool:
        issues.append(
            _issue("VE001", "authoring.define_tool is not allowed in enterprise mode")
        )
    tenancy = tds.security.tenancy
    tenant_mode = tenancy.mode
    for tool in tds.tools:
        has_must = bool(tool.static_filters.must)
        if tenant_mode == "none" and not has_must:
            issues.append(
                _issue(
                    "VE002",
                    "enterprise mode requires tenancy or a static must filter",
                    tool=tool.name,
                )
            )
        if tool.output.limit_max > 100:
            issues.append(
                _issue(
                    "VE003",
                    "output.limit_max must be <= 100 in enterprise mode",
                    tool=tool.name,
                )
            )
    if raw:
        for name, conn in (raw.get("connections") or {}).items():
            if not isinstance(conn, dict):
                continue
            for key in ("url", "dsn", "host"):
                val = conn.get(key)
                if isinstance(val, str) and val and not val.startswith("${"):
                    issues.append(
                        _issue(
                            "VE004",
                            f"connection '{name}.{key}' must use ${{VAR}}",
                            path=f"connections.{name}.{key}",
                        )
                    )
    if meta_tools_enabled:
        issues.append(
            _issue(
                "VE005",
                "serve meta tools should be disabled (--no-meta-tools)",
                severity="warning",
            )
        )
    if tds.defaults.embedding.provider == "fastembed":
        issues.append(
            _issue(
                "VE007",
                "fastembed is not recommended in enterprise; use a remote provider with dims",
                severity="warning",
            )
        )
    return issues
