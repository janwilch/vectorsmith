"""In-process Prometheus text when observability.metrics.enabled. Off = no counters."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

_enabled = False
_calls: dict[tuple[str, str], int] = defaultdict(int)
_latency: dict[str, list[float]] = defaultdict(list)
_embed: dict[str, int] = defaultdict(int)
_adapter_err: dict[tuple[str, str], int] = defaultdict(int)
_rl: dict[str, int] = defaultdict(int)


def configure_metrics(enabled: bool = False) -> None:
    global _enabled
    _enabled = bool(enabled)
    if not _enabled:
        return


def enabled() -> bool:
    return _enabled


def inc_tool_call(tool: str, status: str) -> None:
    if _enabled:
        _calls[(tool, status)] += 1


def observe_latency(tool: str, seconds: float) -> None:
    if _enabled:
        _latency[tool].append(seconds)


def inc_embed(provider: str) -> None:
    if _enabled:
        _embed[provider] += 1


def inc_adapter_error(backend: str, code: str) -> None:
    if _enabled:
        _adapter_err[(backend, code)] += 1


def inc_rate_limit(tool: str) -> None:
    if _enabled:
        _rl[tool] += 1


def reset() -> None:
    _calls.clear()
    _latency.clear()
    _embed.clear()
    _adapter_err.clear()
    _rl.clear()


def render() -> str:
    lines = [
        "# TYPE vectorsmith_tool_calls_total counter",
    ]
    for (tool, status), n in sorted(_calls.items()):
        lines.append(f'vectorsmith_tool_calls_total{{tool="{tool}",status="{status}"}} {n}')
    lines.append("# TYPE vectorsmith_tool_latency_seconds summary")
    for tool, samples in sorted(_latency.items()):
        if not samples:
            continue
        lines.append(
            f'vectorsmith_tool_latency_seconds{{tool="{tool}"}} {sum(samples) / len(samples)}'
        )
    lines.append("# TYPE vectorsmith_embed_requests_total counter")
    for provider, n in sorted(_embed.items()):
        lines.append(f'vectorsmith_embed_requests_total{{provider="{provider}"}} {n}')
    lines.append("# TYPE vectorsmith_adapter_errors_total counter")
    for (backend, code), n in sorted(_adapter_err.items()):
        lines.append(f'vectorsmith_adapter_errors_total{{backend="{backend}",code="{code}"}} {n}')
    lines.append("# TYPE vectorsmith_rate_limit_hits_total counter")
    for tool, n in sorted(_rl.items()):
        lines.append(f'vectorsmith_rate_limit_hits_total{{tool="{tool}"}} {n}')
    return "\n".join(lines) + "\n"


def snapshot() -> dict[str, Any]:
    return {
        "calls": dict(_calls),
        "embed": dict(_embed),
        "rate_limit": dict(_rl),
    }
