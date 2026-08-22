"""Compile ToolSpec → MCP schema + filter template + execution plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vectorsmith_core.ir.filter import Cond, ParamRef, parse_ir
from vectorsmith_core.tds.models import (
    EmbeddingConfig,
    ParamSpec,
    RetrieveStep,
    ToolSpec,
)

_JSON_TYPE = {
    "keyword": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
    "datetime": "string",
    "keyword[]": "array",
    "unknown": "string",
}

_ARRAY_OPS = frozenset({"in", "nin", "contains_any", "contains_all"})


@dataclass
class ExecutionPlan:
    kind: str
    connection: str | None
    collection: str | object | None
    query_param: str | None
    query_required: bool
    mode: str
    alpha: float
    embedding: str | None
    fetch_k_param: str
    overfetch_factor: int
    max_candidates: int
    projection: list[str] | None
    limit_default: int
    limit_max: int
    include_score: bool
    min_score: float | None = None
    search_ef: int | None = None
    static_conds: list[Cond] = field(default_factory=list)
    static_must: list[Cond] = field(default_factory=list)
    static_must_not: list[Cond] = field(default_factory=list)
    param_conds: list[Cond] = field(default_factory=list)
    steps: list[object] | None = None
    is_synthetic: bool = False
    embed_spec: EmbeddingConfig | None = None
    param_resolve: dict[str, Any] = field(default_factory=dict)
    include_id: bool = True
    max_field_length: int | None = None
    truncate_suffix: str = "…"
    output_redact: list[Any] = field(default_factory=list)
    expand: Any | None = None
    rerank: Any | None = None


def _prop(p: ParamSpec) -> dict[str, Any]:
    typ = _JSON_TYPE.get(str(p.dtype), "string")
    schema: dict[str, Any]
    if p.op in _ARRAY_OPS or p.dtype == "keyword[]":
        item = "string" if p.dtype in {"keyword", "keyword[]", "datetime"} else typ
        if p.dtype == "integer":
            item = "integer"
        elif p.dtype == "float":
            item = "number"
        schema = {"type": "array", "items": {"type": item}}
    elif p.dtype == "datetime":
        schema = {"type": "string", "format": "date-time"}
    else:
        schema = {"type": typ}
    if p.enum and not (p.resolve and p.resolve.kind == "directory"):
        if schema.get("type") == "array":
            schema["items"]["enum"] = list(p.enum)
        else:
            schema["enum"] = list(p.enum)
    if p.description:
        schema["description"] = p.description
    if p.default is not None:
        schema["default"] = p.default
    if p.max is not None and typ in {"integer", "number"}:
        schema["maximum"] = p.max
    return schema


def mcp_schema(tool: ToolSpec) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    if tool.query is not None:
        props[tool.query.param] = {"type": "string"}
        if tool.query.required:
            required.append(tool.query.param)
    for p in tool.parameters:
        props[p.name] = _prop(p)
        if p.required:
            required.append(p.name)
    if tool.kind not in {"lookup", "count", "meta"}:
        props.setdefault(
            "limit",
            {
                "type": "integer",
                "minimum": 1,
                "maximum": tool.output.limit_max,
                "default": tool.output.limit_default,
            },
        )
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


def _as_embed(value: Any) -> EmbeddingConfig | None:
    if value is None:
        return None
    if isinstance(value, EmbeddingConfig):
        return value
    if isinstance(value, str):
        return EmbeddingConfig.from_legacy(value)
    return None


def _plan_embedding(
    query: Any,
    retrieve: Any,
    default_embedding: EmbeddingConfig | str | None,
) -> tuple[str | None, EmbeddingConfig | None]:
    spec = None
    if query is not None and getattr(query, "embedding", None):
        spec = _as_embed(query.embedding)
    if spec is None:
        rq = getattr(retrieve, "query", None) if retrieve is not None else None
        if rq is not None and getattr(rq, "embedding", None):
            spec = _as_embed(rq.embedding)
    if spec is None:
        spec = _as_embed(default_embedding)
    if spec is None:
        return None, None
    return spec.identity, spec


def compile_tool(
    tool: ToolSpec,
    *,
    default_embedding: EmbeddingConfig | str | None = None,
) -> tuple[dict[str, Any], ExecutionPlan]:
    block = tool.static_filters
    static = [Cond(path=sf.path, op=sf.op, value=sf.value) for sf in block.must]
    static_not = [Cond(path=sf.path, op=sf.op, value=sf.value) for sf in block.must_not]
    params = [
        Cond(path=p.path or p.name, op=p.op or "eq", value=ParamRef(p.name))
        for p in tool.parameters
        if p.path or p.op
    ]
    query = tool.query
    retrieve = None
    if tool.steps:
        first = tool.steps[0]
        retrieve = first.retrieve if isinstance(first, RetrieveStep) else None
    target = tool.target or (retrieve.target if retrieve else None)
    fetch = retrieve.fetch if retrieve else None
    embedding, embed_spec = _plan_embedding(query, retrieve, default_embedding)
    plan = ExecutionPlan(
        kind=tool.kind,
        connection=target.connection if target else None,
        collection=target.collection if target else None,
        query_param=query.param
        if query
        else (retrieve.query.param if retrieve and retrieve.query else None),
        query_required=bool(query.required) if query else False,
        mode=(query.mode if query else "dense"),
        alpha=query.alpha if query else 0.5,
        embedding=embedding,
        embed_spec=embed_spec,
        fetch_k_param=fetch.k_param if fetch else "limit",
        overfetch_factor=fetch.overfetch_factor if fetch else 10,
        max_candidates=fetch.max_candidates if fetch else 2000,
        projection=list(tool.output.fields) if tool.output.fields else None,
        limit_default=tool.output.limit_default,
        limit_max=tool.output.limit_max,
        include_score=tool.output.include_score,
        include_id=tool.output.include_id,
        max_field_length=tool.output.max_field_length,
        truncate_suffix=tool.output.truncate_suffix,
        output_redact=list(tool.output.redact),
        expand=(
            query.expand
            if query is not None
            else (retrieve.query.expand if retrieve and retrieve.query else None)
        ),
        rerank=tool.rerank,
        min_score=(
            query.min_score
            if query is not None
            else (retrieve.query.min_score if retrieve and retrieve.query else None)
        ),
        search_ef=(
            query.ef
            if query is not None
            else (retrieve.query.ef if retrieve and retrieve.query else None)
        ),
        static_conds=static,
        static_must=static,
        static_must_not=static_not,
        param_conds=params,
        param_resolve={
            p.name: {"resolve": p.resolve, "enum": list(p.enum or [])}
            for p in tool.parameters
            if p.resolve is not None
        },
        steps=list(tool.steps) if tool.steps else None,
        is_synthetic=tool._synthetic,
    )
    if retrieve and retrieve.filter:
        parsed = parse_ir(retrieve.filter)
        if parsed is not None:
            plan.param_conds.append(parsed)  # type: ignore[arg-type]
    return mcp_schema(tool), plan
