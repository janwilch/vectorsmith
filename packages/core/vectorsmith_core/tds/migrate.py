"""TDS version migrations (v1 → v2)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def migrate_document(data: dict[str, Any], *, from_version: str, to_version: str) -> dict[str, Any]:
    if from_version == to_version:
        return deepcopy(data)
    if from_version != "1" or to_version != "2":
        raise ValueError(f"unsupported migration {from_version} → {to_version}")
    out = deepcopy(data)
    out["tds_version"] = "2"
    out.setdefault("meta", {})
    for tool in out.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        sf = tool.get("static_filters")
        if isinstance(sf, list):
            tool["static_filters"] = {"must": sf}
    return out
