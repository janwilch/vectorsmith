"""T4: TDS models — valid and invalid fixtures including table/hybrid/authoring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vectorsmith_core.tds.models import TDSFile, ToolSpec, is_table_mode

MIN_DESC = "Search invoices by client status and due date."


def _base_conn(backend: str = "qdrant", **extra: object) -> dict[str, object]:
    if backend == "qdrant":
        return {"backend": "qdrant", "url": "${QDRANT_URL}", **extra}
    if backend == "pgvector":
        return {"backend": "pgvector", "dsn": "${PG_DSN}", **extra}
    if backend == "chroma":
        return {"backend": "chroma", "url": "${CHROMA_URL}", **extra}
    if backend == "pinecone":
        return {
            "backend": "pinecone",
            "api_key": "${PINECONE_API_KEY}",
            "host": "${PINECONE_HOST}",
            **extra,
        }
    if backend == "weaviate":
        return {"backend": "weaviate", "url": "${WEAVIATE_URL}", **extra}
    if backend == "milvus":
        return {"backend": "milvus", "uri": "${MILVUS_URI}", **extra}
    raise AssertionError(backend)


def _search_tool(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "search_invoices",
        "description": MIN_DESC,
        "kind": "search",
        "target": {"connection": "main", "collection": "invoices"},
    }
    base.update(kwargs)
    return base


def _file(tools: list[object] | None = None, backend: str = "qdrant", **kw: object) -> dict:
    data: dict[str, object] = {
        "tds_version": "1",
        "connections": {"main": _base_conn(backend)},
        "tools": tools if tools is not None else [_search_tool()],
    }
    data.update(kw)
    return data


@pytest.mark.parametrize(
    "backend",
    ["qdrant", "pgvector", "chroma", "pinecone", "weaviate", "milvus"],
)
def test_valid_each_backend(backend: str) -> None:
    TDSFile.model_validate(_file(backend=backend))


def test_hybrid_query() -> None:
    t = _search_tool(query={"param": "query", "mode": "hybrid", "alpha": 0.3})
    TDSFile.model_validate(_file(tools=[t]))


def test_authoring_block() -> None:
    tds = TDSFile.model_validate(_file(authoring={"define_tool": True}))
    assert tds.authoring.define_tool is True


def test_table_mode_via_mode() -> None:
    tds = TDSFile.model_validate(
        _file(backend="pgvector", connections={"main": _base_conn("pgvector", mode="table")})
    )
    conn = tds.connections["main"]
    assert conn.backend == "pgvector"
    assert is_table_mode(conn)


def test_table_mode_via_null_vector_column() -> None:
    tds = TDSFile.model_validate(
        _file(
            backend="pgvector",
            connections={"main": _base_conn("pgvector", vector_column=None)},
        )
    )
    assert is_table_mode(tds.connections["main"])


def test_pipeline_requires_retrieve_first() -> None:
    pipe = {
        "name": "top_overdue_by_client",
        "description": MIN_DESC,
        "kind": "pipeline",
        "steps": [
            {
                "retrieve": {
                    "target": {"connection": "main", "collection": "invoices"},
                }
            },
            {"project": {"fields": ["invoice_id"]}},
        ],
        "parameters": [{"name": "limit", "dtype": "integer", "default": 10}],
    }
    TDSFile.model_validate(_file(tools=[pipe]))


def test_pipeline_without_retrieve_fails() -> None:
    pipe = {
        "name": "bad_pipeline_tool",
        "description": MIN_DESC,
        "kind": "pipeline",
        "steps": [{"project": {"fields": ["invoice_id"]}}],
    }
    with pytest.raises(ValidationError):
        ToolSpec.model_validate(pipe)


def test_duplicate_tool_names() -> None:
    with pytest.raises(ValidationError):
        TDSFile.model_validate(_file(tools=[_search_tool(), _search_tool()]))


def test_unknown_connection() -> None:
    t = _search_tool()
    t["target"] = {"connection": "missing", "collection": "x"}
    with pytest.raises(ValidationError):
        TDSFile.model_validate(_file(tools=[t]))


def test_bad_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolSpec.model_validate(_search_tool(name="BadName"))


def test_short_description() -> None:
    with pytest.raises(ValidationError):
        ToolSpec.model_validate(_search_tool(description="too short"))


def test_lookup_and_count_and_scroll() -> None:
    for kind in ("lookup", "count", "scroll"):
        TDSFile.model_validate(
            _file(tools=[_search_tool(name=f"{kind}_invoices", kind=kind)])
        )


def test_meta_forbids_query() -> None:
    with pytest.raises(ValidationError):
        ToolSpec.model_validate(
            {
                "name": "list_things_meta",
                "description": MIN_DESC,
                "kind": "meta",
                "query": {"param": "query"},
            }
        )


def test_pinecone_namespace_and_weaviate_tenant() -> None:
    tds = TDSFile.model_validate(
        {
            "tds_version": "1",
            "connections": {
                "pc": {**_base_conn("pinecone"), "namespace": "acme"},
                "wv": {**_base_conn("weaviate"), "tenant": "t1"},
                "mv": {**_base_conn("milvus"), "database": "default"},
            },
            "tools": [
                _search_tool(
                    name="search_ns",
                    target={"connection": "pc", "collection": "acme"},
                )
            ],
        }
    )
    assert tds.connections["pc"].namespace == "acme"  # type: ignore[union-attr]
    assert tds.connections["wv"].tenant == "t1"  # type: ignore[union-attr]


def test_unknown_backend_rejected() -> None:
    with pytest.raises(ValidationError):
        TDSFile.model_validate(
            {
                "tds_version": "1",
                "connections": {"main": {"backend": "redis", "url": "x"}},
                "tools": [_search_tool()],
            }
        )
