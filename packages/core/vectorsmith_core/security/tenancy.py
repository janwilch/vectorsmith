"""Bind claim/header identity onto ``CallContext`` and the store filter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vectorsmith_core.api import CallContext, CompiledTool
from vectorsmith_core.errors import AuthError, InvalidArgumentsError
from vectorsmith_core.ir.filter import Cond, ParamRef
from vectorsmith_core.tds.models import TenancyConfig


def _header(headers: Mapping[str, str], name: str) -> str | None:
    want = name.lower()
    for key, val in headers.items():
        if str(key).lower() == want and val not in {None, ""}:
            return str(val)
    return None


def bind_tenancy(
    tenancy: TenancyConfig,
    ctx: CallContext,
    *,
    headers: Mapping[str, str] | None = None,
) -> CallContext:
    """Resolve ``tenant_value`` / ``tenant_filter`` from claims or headers."""
    if tenancy.mode in {"none", "static"}:
        return ctx
    value = ctx.tenant_value
    if value is None:
        if tenancy.mode == "claim" and tenancy.claim:
            raw = ctx.claims.get(tenancy.claim)
            if raw is not None and raw != "":
                value = str(raw)
        elif tenancy.mode == "header" and headers is not None:
            value = _header(headers, tenancy.header)
    if value is None:
        return ctx
    ctx.tenant_value = value
    ctx.tenant_filter = Cond(path=tenancy.path, op=tenancy.op, value=value)
    return ctx


def require_tenancy(tenancy: TenancyConfig, ctx: CallContext) -> None:
    if tenancy.mode in {"claim", "header"} and ctx.tenant_filter is None:
        raise AuthError(detail="tenancy value is required")


def enforce_tenancy(
    tenancy: TenancyConfig,
    compiled: CompiledTool,
    args: dict[str, Any],
    ctx: CallContext,
) -> list[str]:
    """Apply ``enforce`` when the model passed a colliding tenancy argument."""
    if tenancy.mode in {"none", "static"} or ctx.tenant_value is None:
        return []
    tenant = ctx.tenant_value
    names: list[str] = []
    plan = compiled.plan
    if plan is not None:
        for cond in plan.param_conds:
            if cond.path == tenancy.path and isinstance(cond.value, ParamRef):
                names.append(cond.value.name)
    if tenancy.path in args and tenancy.path not in names:
        names.append(tenancy.path)
    warnings: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen or name not in args:
            continue
        seen.add(name)
        if args[name] == tenant:
            continue
        if tenancy.enforce == "strict":
            raise InvalidArgumentsError(
                code="VB4010",
                detail=f"VB4010 argument '{name}' conflicts with tenancy '{tenancy.path}'",
            )
        args[name] = tenant
        if tenancy.enforce == "warn":
            warnings.append("VB4010")
    return warnings
