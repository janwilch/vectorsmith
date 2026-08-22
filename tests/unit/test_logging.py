"""Structured JSON logs vs default text."""

from __future__ import annotations

import json
import logging

from vectorsmith_cli.observe.logging import JsonFormatter, configure_logging


def test_json_formatter_includes_request_id() -> None:
    record = logging.LogRecord(
        name="vectorsmith.call",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="tool call completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.principal = "alice"
    record.tool = "search_invoices"
    record.latency_ms = 12
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "req-1"
    assert payload["principal"] == "alice"
    assert payload["tool"] == "search_invoices"
    assert payload["latency_ms"] == 12
    assert payload["level"] == "info"
    assert payload["msg"] == "tool call completed"


def test_default_text_format(caplog: logging.LogCaptureFixture) -> None:
    configure_logging("text", "info")
    log = logging.getLogger("vectorsmith")
    log.addHandler(caplog.handler)
    log.info("hello")
    assert "hello" in caplog.text
    assert not caplog.text.strip().startswith("{")
