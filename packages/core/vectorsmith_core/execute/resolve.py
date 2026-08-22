"""Directory / fuzzy parameter resolvers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from vectorsmith_core.tds.models import ResolveSpec

_CACHE: dict[tuple[str, str, str], tuple[float, list[str]]] = {}


@dataclass
class ResolveResult:
    value: str | None
    confidence: float
    alternatives: list[str] = field(default_factory=list)
    error: str | None = None


def _norm(text: str) -> str:
    return " ".join(str(text).casefold().split())


def _score(raw: str, candidate: str) -> float:
    a, b = _norm(raw), _norm(candidate)
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def clear_directory_cache() -> None:
    _CACHE.clear()


def seed_directory_cache(
    connection: str, collection: str, field: str, values: list[str], *, ttl_s: int = 600
) -> None:
    _CACHE[(connection, collection, field)] = (time.time() + ttl_s, list(values))


async def load_directory(
    adapter: Any,
    spec: ResolveSpec,
    *,
    connection: str,
    collection: str,
) -> list[str]:
    field = spec.field or "name"
    key = (connection, collection, field)
    hit = _CACHE.get(key)
    now = time.time()
    if hit and hit[0] > now:
        return hit[1]
    rows = await adapter.sample(collection, spec.max_candidates)
    values: list[str] = []
    seen: set[str] = set()
    for row in rows:
        val = row.get(field)
        if val is None:
            continue
        text = str(val)
        if text not in seen:
            seen.add(text)
            values.append(text)
    _CACHE[key] = (now + spec.cache_ttl_s, values)
    return values


def resolve_from_enum(raw: str, enum: list[Any]) -> ResolveResult | None:
    for item in enum:
        if _norm(str(item)) == _norm(raw):
            return ResolveResult(value=str(item), confidence=1.0)
    return None


async def resolve_value(
    raw: str,
    spec: ResolveSpec,
    *,
    adapter: Any,
    connection: str,
    collection: str,
    enum: list[Any] | None = None,
) -> ResolveResult:
    if enum:
        exact = resolve_from_enum(raw, enum)
        if exact is not None:
            return exact
    if spec.kind != "directory":
        return ResolveResult(value=raw, confidence=1.0)
    values = await load_directory(
        adapter, spec, connection=connection, collection=collection
    )
    ranked = sorted(((_score(raw, v), v) for v in values), reverse=True)
    if not ranked:
        return ResolveResult(
            value=None,
            confidence=0.0,
            error=f"Could not resolve '{raw}'.",
        )
    best, name = ranked[0]
    alts = [v for s, v in ranked[1:4] if s >= 0.4]
    if best >= spec.min_confidence:
        return ResolveResult(value=name, confidence=best, alternatives=alts)
    hint = ", ".join([name, *alts][:3])
    return ResolveResult(
        value=None,
        confidence=best,
        alternatives=[name, *alts],
        error=f"Could not resolve '{raw}'. Did you mean: {hint}?",
    )
