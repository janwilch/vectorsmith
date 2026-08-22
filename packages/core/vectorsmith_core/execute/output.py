"""Post-adapter output policy: redact, mask, truncate."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from vectorsmith_core.compilepkg.compiler import ExecutionPlan
from vectorsmith_core.tds.models import OutputRedactRule


def _hash8(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _mask_email(value: str) -> str:
    if "@" in value:
        return "***@" + value.rsplit("@", 1)[1]
    return "***"


def _apply_rule(value: object, rule: OutputRedactRule) -> object:
    if value is None:
        return None
    text = str(value)
    if rule.mode == "omit":
        return None
    if rule.mode == "hash":
        return _hash8(text)
    if rule.mode == "mask":
        return _mask_email(text)
    if rule.mode == "pattern":
        out = text
        for pat in rule.patterns or []:
            out = re.sub(pat.regex, pat.replacement, out)
        return out
    return value


def apply_output_policy(rows: list[dict[str, Any]], plan: ExecutionPlan) -> list[dict[str, Any]]:
    suffix = plan.truncate_suffix or "…"
    max_len = plan.max_field_length
    rules = {r.path: r for r in (plan.output_redact or [])}
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, val in row.items():
            if key == "_id" and not plan.include_id:
                continue
            rule = rules.get(key)
            if rule is not None:
                if rule.mode == "omit":
                    continue
                val = _apply_rule(val, rule)
            if max_len is not None and isinstance(val, str) and len(val) > max_len:
                val = val[: max(0, max_len - len(suffix))] + suffix
            item[key] = val
        out.append(item)
    return out
