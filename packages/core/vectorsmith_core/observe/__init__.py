"""Observability helpers (audit, optional tracing/metrics)."""

from vectorsmith_core.observe.audit import AuditEvent, build_audit_event, redact_args
from vectorsmith_core.observe.metrics import configure_metrics
from vectorsmith_core.observe.metrics import render as render_metrics
from vectorsmith_core.observe.tracing import configure_tracing, start_span

__all__ = [
    "AuditEvent",
    "build_audit_event",
    "configure_metrics",
    "configure_tracing",
    "redact_args",
    "render_metrics",
    "start_span",
]
