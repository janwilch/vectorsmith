"""Apply ``profiles.enterprise.security.hardening`` at serve time."""

from __future__ import annotations

from vectorsmith_core.tds.models import HardeningSpec, TDSFile


def enterprise_hardening(tds: TDSFile) -> HardeningSpec | None:
    profile = tds.profiles.enterprise
    if profile is None:
        return None
    return profile.security.hardening


def apply_serve_hardening(
    tds: TDSFile, *, enable_define: bool, include_meta: bool
) -> tuple[bool, bool]:
    spec = enterprise_hardening(tds)
    if spec is None:
        return enable_define, include_meta
    if spec.disable_authoring:
        enable_define = False
    if spec.disable_meta_tools:
        include_meta = False
    return enable_define, include_meta


def apply_serve_hardening_many(
    files: list[TDSFile], *, enable_define: bool, include_meta: bool
) -> tuple[bool, bool]:
    """Union enterprise flags: any YAML that disables authoring/meta wins."""
    for tds in files:
        enable_define, include_meta = apply_serve_hardening(
            tds, enable_define=enable_define, include_meta=include_meta
        )
    return enable_define, include_meta


def hardening_blocks_authoring(tds: TDSFile) -> bool:
    spec = enterprise_hardening(tds)
    return spec is not None and spec.disable_authoring


def serve_hardening_errors(tds: TDSFile) -> list[str]:
    spec = enterprise_hardening(tds)
    if spec is None:
        return []
    errors: list[str] = []
    if spec.require_tenancy:
        tenant_mode = tds.security.tenancy.mode
        for tool in tds.tools:
            if tenant_mode == "none" and not tool.static_filters.must:
                errors.append(
                    f"profiles.enterprise.require_tenancy: tool '{tool.name}' "
                    "needs tenancy or a static must filter"
                )
    for tool in tds.tools:
        if tool.output.limit_max > spec.max_limit_max:
            errors.append(
                f"profiles.enterprise.max_limit_max: tool '{tool.name}' "
                f"limit_max {tool.output.limit_max} exceeds {spec.max_limit_max}"
            )
    if spec.allowed_backends:
        allowed = set(spec.allowed_backends)
        for name, conn in tds.connections.items():
            if conn.backend not in allowed:
                errors.append(
                    f"profiles.enterprise.allowed_backends: connection '{name}' "
                    f"uses '{conn.backend}'"
                )
    return errors
