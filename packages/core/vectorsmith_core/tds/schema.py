"""Generate committed ``schema_v1.json`` from the pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

from vectorsmith_core.tds.models import TDSFile

SCHEMA_PATH = Path(__file__).with_name("schema_v1.json")


def generate_schema() -> dict:
    return TDSFile.model_json_schema()


def write_schema(path: Path = SCHEMA_PATH) -> None:
    path.write_text(json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n")
