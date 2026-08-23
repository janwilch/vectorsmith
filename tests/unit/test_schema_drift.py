"""T7: committed schema_v1.json matches generated model schema."""

from __future__ import annotations

import json

from vectorsmith_core.tds.schema import (
    SCHEMA_PATH,
    SCHEMA_V2_PATH,
    generate_schema,
    generate_schema_v2,
)


def test_schema_matches_committed() -> None:
    generated = json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n"
    committed = SCHEMA_PATH.read_text()
    assert generated == committed


def test_schema_v2_matches_committed() -> None:
    generated = json.dumps(generate_schema_v2(), indent=2, sort_keys=True) + "\n"
    committed = SCHEMA_V2_PATH.read_text()
    assert generated == committed


def test_schema_v2_documents_shared_structure() -> None:
    v2 = generate_schema_v2()
    assert "TDS v2 shares the v1 structural schema" in str(v2.get("$comment"))
