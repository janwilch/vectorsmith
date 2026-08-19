"""Sampling-based type inference."""

from __future__ import annotations

from datetime import datetime
from typing import Any

TYPE_MAJORITY = 0.99
DATETIME_STR = 0.95
ENUM_MAX_DISTINCT = 25
ENUM_MIN_SAMPLES = 30
SAMPLE_N = 200
MAX_DEPTH = 2


def infer_fields(
    rows: list[dict[str, Any]],
    *,
    redact_examples: bool = False,
    max_depth: int = MAX_DEPTH,
) -> list[dict[str, Any]]:
    """Infer field schemas from a sample of payload dicts."""
    histogram: dict[str, dict[str, Any]] = {}
    for row in rows:
        _walk(row, "", histogram, 0, max_depth)
    out: list[dict[str, Any]] = []
    n = max(len(rows), 1)
    for path, info in sorted(histogram.items()):
        types: dict[str, int] = info["types"]
        present = info["present"]
        null_rate = 1.0 - (present / n)
        majority = max(types, key=lambda k: types[k]) if types else "unknown"
        share = (types.get(majority, 0) / present) if present else 0.0
        dtype = majority if share >= TYPE_MAJORITY else "unknown"
        if dtype == "keyword":
            iso = info["iso"] / present if present else 0.0
            if iso >= DATETIME_STR:
                dtype = "datetime"
        distinct = info["distinct"]
        enum = None
        if (
            dtype == "keyword"
            and present >= ENUM_MIN_SAMPLES
            and 0 < len(distinct) <= ENUM_MAX_DISTINCT
        ):
            enum = sorted(distinct, key=str)[:ENUM_MAX_DISTINCT]
        examples = [] if redact_examples else info["examples"][:3]
        out.append(
            {
                "path": path,
                "dtype": dtype,
                "null_rate": round(null_rate, 4),
                "enum": enum,
                "examples": examples,
            }
        )
    return out


def _walk(
    obj: object,
    prefix: str,
    histogram: dict[str, dict[str, Any]],
    depth: int,
    max_depth: int,
) -> None:
    if not isinstance(obj, dict) or depth > max_depth:
        return
    for key, val in obj.items():
        if str(key).startswith("_"):
            continue
        path = f"{prefix}.{key}" if prefix else str(key)
        slot = histogram.setdefault(
            path,
            {"types": {}, "present": 0, "distinct": set(), "examples": [], "iso": 0},
        )
        if val is None:
            continue
        slot["present"] += 1
        kind = _kind(val)
        slot["types"][kind] = slot["types"].get(kind, 0) + 1
        if kind == "keyword" and isinstance(val, str):
            slot["distinct"].add(val)
            if _is_iso(val):
                slot["iso"] += 1
        if len(slot["examples"]) < 3 and not isinstance(val, (dict, list)):
            slot["examples"].append(val)
        if isinstance(val, dict) and depth < max_depth:
            _walk(val, path, histogram, depth + 1, max_depth)


def _kind(val: object) -> str:
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    if isinstance(val, list):
        return "keyword[]"
    if isinstance(val, str):
        return "keyword"
    return "unknown"


def _is_iso(val: str) -> bool:
    if len(val) < 8:
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            datetime.strptime(val[: len(fmt) + 8].rstrip("Z"), fmt.replace("Z", ""))
            return True
        except ValueError:
            continue
    return False
