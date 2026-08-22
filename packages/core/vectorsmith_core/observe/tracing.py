"""Optional tracing. Disabled by default — start_span is a no-op singleton."""

from __future__ import annotations

from contextlib import suppress
from typing import Any, Literal

_enabled = False
_service = "vectorsmith"
_recorded: list[tuple[str, dict[str, Any]]] = []
_stack: list[str] = []


class _Noop:
    __slots__ = ()

    def __enter__(self) -> _Noop:
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        return False

    def set_attribute(self, *_a: object, **_k: object) -> None:
        return None


_NOOP = _Noop()


class _MemSpan:
    def __init__(self, name: str, attrs: dict[str, Any]) -> None:
        self.name = name
        self.attrs = attrs
        self._otel: Any = None

    def __enter__(self) -> _MemSpan:
        _stack.append(self.name)
        _recorded.append((self.name, dict(self.attrs)))
        self._otel = _start_otel(self.name, self.attrs)
        return self

    def __exit__(self, *args: object) -> Literal[False]:
        if _stack and _stack[-1] == self.name:
            _stack.pop()
        if self._otel is not None:
            with suppress(Exception):
                self._otel.__exit__(*args)
        return False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attrs[key] = value


def configure_tracing(enabled: bool = False, *, service_name: str = "vectorsmith") -> None:
    global _enabled, _service
    _enabled = bool(enabled)
    _service = service_name
    if _enabled:
        _try_otel()


def _try_otel() -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({"service.name": _service})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
    except Exception:
        return


def _start_otel(name: str, attrs: dict[str, Any]) -> Any:
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("vectorsmith")
        span_cm = tracer.start_as_current_span(name)
        span = span_cm.__enter__()
        for key, val in attrs.items():
            if val is not None:
                span.set_attribute(key, val)
        return span_cm
    except Exception:
        return None


def start_span(name: str, **attrs: Any) -> Any:
    if not _enabled:
        return _NOOP
    return _MemSpan(name, attrs)


def recorded_spans() -> list[tuple[str, dict[str, Any]]]:
    return list(_recorded)


def reset_spans() -> None:
    _recorded.clear()
    _stack.clear()
