"""Process logging for ``vectorsmith serve``."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_SAFE_KEYS = ("request_id", "principal", "tool", "latency_ms", "trace_id", "span_id")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "ts": datetime.now(UTC).isoformat(),
            "msg": record.getMessage(),
        }
        for key in _SAFE_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if "trace_id" not in payload:
            from vectorsmith_core.observe.tracing import current_trace_context

            payload.update(current_trace_context())
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(fmt: str = "text", level: str = "info") -> None:
    root = logging.getLogger("vectorsmith")
    root.handlers.clear()
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False
