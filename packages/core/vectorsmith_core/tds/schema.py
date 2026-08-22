"""Generate committed ``schema_v1.json`` from the pydantic models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vectorsmith_core.tds.models import TDSFile

SCHEMA_PATH = Path(__file__).with_name("schema_v1.json")
SCHEMA_V2_PATH = Path(__file__).with_name("schema_v2.json")


def generate_schema() -> dict[str, Any]:
    return TDSFile.model_json_schema()


def write_schema(path: Path = SCHEMA_PATH) -> None:
    path.write_text(json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n")


def write_schema_v2(path: Path = SCHEMA_V2_PATH) -> None:
    write_schema(path)
