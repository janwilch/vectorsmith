"""defaults.embedding flows into the compiled plan; per-tool query.embedding wins."""

from __future__ import annotations

from vectorsmith_core.api import load_project


def _base() -> dict:
    return {
        "tds_version": "1",
        "connections": {"main": {"backend": "qdrant", "url": "http://localhost:6333"}},
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "query": {"param": "query"},
            }
        ],
    }


def test_defaults_embedding_on_plan() -> None:
    src = _base()
    src["defaults"] = {"embedding": "BAAI/custom-default-model"}
    project = load_project(src, env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.embedding == "BAAI/custom-default-model"


def test_query_embedding_overrides_defaults() -> None:
    src = _base()
    src["defaults"] = {"embedding": "defaults/should-not-win"}
    src["tools"][0]["query"] = {"param": "query", "embedding": "tool/override"}
    project = load_project(src, env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.embedding == "tool/override"


def test_tds_default_when_defaults_omitted() -> None:
    project = load_project(_base(), env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.embedding == "fastembed/BAAI/bge-small-en-v1.5"


def test_defaults_embedding_without_query_block() -> None:
    src = _base()
    del src["tools"][0]["query"]
    src["defaults"] = {"embedding": "defaults/no-query"}
    project = load_project(src, env={"QDRANT_URL": "http://localhost:6333"})
    plan = project.tools["search_invoices"].plan
    assert plan is not None
    assert plan.embedding == "defaults/no-query"
