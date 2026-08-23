"""Audit sinks: stdout, append-only file (0600), HTTP POST, OTLP logs."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from vectorsmith_core.observe.audit import AuditEvent
from vectorsmith_core.tds.models import AuditConfig

log = logging.getLogger("vectorsmith.audit")


class StdoutSink:
    async def emit(self, event: AuditEvent) -> None:
        print(json.dumps(event, default=str), file=sys.stderr, flush=True)

    async def flush(self) -> None:
        return None


class FileSink:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.close(fd)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    async def emit(self, event: AuditEvent) -> None:
        line = json.dumps(event, default=str) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)

    async def flush(self) -> None:
        return None


class HTTPSink:
    def __init__(self, url: str) -> None:
        self.url = url

    async def emit(self, event: AuditEvent) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(self.url, json=event)

    async def flush(self) -> None:
        return None


class OTLPSink:
    """OTLP HTTP JSON logs (collector ``/v1/logs``), not a raw audit POST."""

    def __init__(self, url: str) -> None:
        dest = url.rstrip("/")
        if not dest.endswith("/v1/logs"):
            dest = f"{dest}/v1/logs"
        self.url = dest

    async def emit(self, event: AuditEvent) -> None:
        import httpx

        payload = {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "vectorsmith"},
                            }
                        ]
                    },
                    "scopeLogs": [
                        {
                            "scope": {"name": "vectorsmith.audit"},
                            "logRecords": [
                                {
                                    "timeUnixNano": str(int(time.time() * 1_000_000_000)),
                                    "severityText": "INFO",
                                    "body": {
                                        "stringValue": json.dumps(event, default=str)
                                    },
                                    "attributes": [
                                        {
                                            "key": "audit.tool",
                                            "value": {
                                                "stringValue": str(event.get("tool") or "")
                                            },
                                        },
                                        {
                                            "key": "audit.request_id",
                                            "value": {
                                                "stringValue": str(
                                                    event.get("request_id") or ""
                                                )
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(self.url, json=payload)

    async def flush(self) -> None:
        return None


def build_audit_sink(
    cfg: AuditConfig,
    *,
    log_path: Path | None = None,
    sink_name: str | None = None,
    url: str | None = None,
) -> Any | None:
    enabled = cfg.enabled or log_path is not None or sink_name is not None or url is not None
    if not enabled:
        return None
    kind = sink_name or cfg.sink
    path = log_path or (Path(cfg.path) if cfg.path else None)
    dest = url or cfg.url
    if kind == "file" or path is not None:
        if path is None:
            path = Path("vectorsmith-audit.jsonl")
        return FileSink(path)
    if kind == "http":
        if not dest:
            log.warning("audit http sink missing url; audit disabled")
            return None
        return HTTPSink(dest)
    if kind == "otlp":
        if not dest:
            log.warning("audit otlp sink missing url; audit disabled")
            return None
        return OTLPSink(dest)
    return StdoutSink()
