"""Tool-level RBAC from ``security.rbac`` + caller role claims."""

from __future__ import annotations

from collections.abc import Iterable

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import AuthError
from vectorsmith_core.tds.models import RBACConfig

_META = frozenset({"list_available_tools", "run_tool"})


def _roles_from_ctx(ctx: CallContext, rbac: RBACConfig) -> list[str]:
    raw = ctx.claims.get(rbac.role_claim)
    if raw is None or raw == "":
        return [rbac.default_role] if rbac.default_role else []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, Iterable):
        return [str(x) for x in raw]
    return [str(raw)]


def allowed_tools(ctx: CallContext, rbac: RBACConfig) -> set[str]:
    names: set[str] = set()
    for role in _roles_from_ctx(ctx, rbac):
        spec = rbac.roles.get(role)
        if spec is None:
            continue
        names.update(spec.allow)
    return names


def check_rbac(
    ctx: CallContext,
    tool_name: str,
    rbac: RBACConfig,
    *,
    allow_meta: bool = False,
) -> None:
    """Raise ``AuthError`` if the caller may not invoke ``tool_name``."""
    if not rbac.enabled:
        return
    if tool_name in rbac.deny_tools:
        raise AuthError(detail=f"tool '{tool_name}' is denied")
    if allow_meta and tool_name in _META:
        return
    allowed = allowed_tools(ctx, rbac)
    if "*" in allowed or tool_name in allowed:
        return
    raise AuthError(detail=f"tool '{tool_name}' not permitted for role")
