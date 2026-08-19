"""T12: load_project façade, built-ins, draft inertness."""

from __future__ import annotations

from vectorsmith_core.api import draft_tool, load_project


def _src(**kw: object) -> dict:
    data: dict = {
        "tds_version": "1",
        "connections": {
            "main": {
                "backend": "qdrant",
                "url": "${QDRANT_URL}",
                "builtin_tools": {"semantic_search": True, "get_by_id": True},
                "builtin_defaults": {
                    "collections": ["invoices"],
                    "static_filters": [{"path": "tenant", "op": "eq", "value": "acme"}],
                },
            }
        },
        "tools": [
            {
                "name": "search_invoices",
                "description": "Search invoices by client status and due date for billing.",
                "target": {"connection": "main", "collection": "invoices"},
                "parameters": [
                    {"name": "client", "path": "client_name", "dtype": "keyword", "op": "eq"}
                ],
            }
        ],
    }
    data.update(kw)
    return data


def test_load_synthesizes_builtins() -> None:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    names = list(project.tools)
    assert "search_invoices" in names
    assert "search_main" in names
    assert "get_main_by_id" in names
    schemas = project.mcp_tool_schemas()
    assert schemas[0]["name"] == "search_invoices"
    assert any(s["name"] == "search_main" for s in schemas)


def test_draft_does_not_mutate_project() -> None:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    before = set(project.tools)
    draft = draft_tool(
        project,
        {"created_by": "define_tool", "conversation_hint": "invoices by due date"},
        {
            "name": "search_invoices_by_due",
            "description": "Search invoices filtered by due date for collections work.",
            "kind": "search",
            "target": {"connection": "main", "collection": "invoices"},
            "parameters": [
                {"name": "due_after", "path": "due_date", "dtype": "datetime", "op": "gte"}
            ],
        },
    )
    assert draft.status == "pending"
    assert set(project.tools) == before
    assert draft.spec.name not in project.mcp_tool_schemas()
    # static filters auto-attached
    paths = [s.path for s in draft.spec.static_filters]
    assert "tenant" in paths


def test_draft_rejects_meta_kind() -> None:
    project = load_project(_src(), env={"QDRANT_URL": "http://localhost:6333"})
    draft = draft_tool(
        project,
        {},
        {
            "name": "list_all_the_things",
            "description": "List every collection available on the connection now.",
            "kind": "meta",
        },
    )
    codes = [i.code for i in draft.validator_issues]
    assert "VB2017" in codes or "VB2014" in codes
