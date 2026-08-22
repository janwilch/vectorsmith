"""Build redacted audit events. Sinks live in the CLI serve path."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, TypedDict

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import VectorSmithError
from vectorsmith_core.tds.models import AuditConfig


class AuditEvent(TypedDict, total=False):
    audit_version: str
    timestamp: str
    request_id: str
    principal: str | None
    tool: str
    connection: str | None
    collection: str | None
    args: dict[str, Any]
    result_count: int | None
    truncated: bool | None
    search_mode: str | None
    latency_ms: int
    warnings: list[str]
    status: str
    error_code: str | None


class AuditSink(Protocol):
    async def emit(self, event: AuditEvent) -> None: ...

    async def flush(self) -> None: ...


def redact_args(args: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    deny = {f.lower() for f in fields}
    out: dict[str, Any] = {}
    for key, val in args.items():
        if str(key).lower() in deny:
            out[key] = "[REDACTED]"
        else:
            out[key] = val
    return out


def build_audit_event(
    *,
    cfg: AuditConfig,
    ctx: CallContext,
    tool: str,
    args: dict[str, Any],
    connection: str | None,
    collection: str | None,
    latency_ms: int,
    result: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> AuditEvent:
    inc = cfg.include
    event: AuditEvent = {
        "audit_version": "1",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_id": ctx.request_id,
        "principal": ctx.principal,
        "tool": tool,
        "connection": connection,
        "collection": str(collection) if collection is not None else None,
        "status": "error" if error is not None else "ok",
        "error_code": None,
    }
    if error is not None:
        event["error_code"] = (
            error.code if isinstance(error, VectorSmithError) else type(error).__name__
        )
    if inc.args:
        event["args"] = redact_args(args, cfg.redact.arg_fields)
    if inc.latency_ms:
        event["latency_ms"] = latency_ms
    if result is not None:
        if inc.result_count:
            event["result_count"] = int(result.get("count") or 0)
            event["truncated"] = bool(result.get("truncated"))
        if inc.search_mode and result.get("search_mode") is not None:
            event["search_mode"] = str(result.get("search_mode"))
        if inc.warnings:
            event["warnings"] = list(result.get("warnings") or [])
    return event
