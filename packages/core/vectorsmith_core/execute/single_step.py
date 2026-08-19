"""Single-step execution (tech §6 steps 4–13)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from vectorsmith_core.adapters.base import SearchRequest
from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.ir.filter import Cond, bind, merge_and

if TYPE_CHECKING:
    from vectorsmith_core.adapters.base import VectorBackendAdapter
    from vectorsmith_core.api import CallContext, CompiledTool, EmbedProvider, ToolResult
    from vectorsmith_core.compilepkg.compiler import ExecutionPlan

MAX_BYTES = 100_000


def _validate_args(schema: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    import jsonschema  # type: ignore[import-untyped]

    props = schema.get("inputSchema") or schema
    try:
        jsonschema.validate(args, props if props.get("type") == "object" else schema["inputSchema"])
    except jsonschema.ValidationError as exc:
        raise InvalidArgumentsError(detail=exc.message) from exc
    return args


async def execute_single(
    compiled: CompiledTool,
    plan: ExecutionPlan,
    args: dict[str, Any],
    *,
    adapter: VectorBackendAdapter,
    embed: EmbedProvider | None,
    ctx: CallContext,
    debug: bool = False,
) -> ToolResult:
    from vectorsmith_core.api import ToolResult

    _ = ctx
    _validate_args(compiled.mcp_schema, args)
    required = {
        p
        for p in (compiled.mcp_schema.get("inputSchema") or {}).get("required", [])
    }
    bound_params = bind(
        merge_and(*plan.param_conds) if plan.param_conds else None,  # type: ignore[arg-type]
        args,
        required=frozenset(required) - {plan.query_param or ""},
    )
    ir = merge_and(*plan.static_conds, bound_params) if plan.static_conds else bound_params
    # static_conds are Cond literals — merge_and accepts IRNode
    if plan.static_conds:
        ir = merge_and(*plan.static_conds, bound_params)

    native = adapter.compile_filter(ir)
    collection = args.get("collection") if plan.collection == "__param__" else plan.collection
    if not isinstance(collection, str):
        raise InvalidArgumentsError(detail="collection is required")

    warnings: list[str] = []
    search_mode: str = "none"
    vector: list[float] | None = None
    query_text = args.get(plan.query_param) if plan.query_param else None

    if plan.kind == "meta":
        names = await adapter.list_collections()
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        for name in names:
            try:
                n = await adapter.count(name, None)
                rows.append({"collection": name, "approx_count": n})
            except Exception:  # noqa: BLE001 — count is best-effort for meta
                rows.append({"collection": name, "approx_count": None})
                warnings.append("VB4003")
        return ToolResult(rows=rows, count=len(rows), search_mode="none", warnings=warnings)

    if plan.kind == "count":
        n = await adapter.count(collection, ir)
        return ToolResult(rows=[{"count": n}], count=n, search_mode="none")

    if query_text:
        if embed is None:
            raise InvalidArgumentsError(detail="query provided but no embed provider configured")
        model = plan.embedding or "fastembed/BAAI/bge-small-en-v1.5"
        vectors = await embed.embed([str(query_text)], model)
        vector = vectors[0]
        search_mode = plan.mode
    elif plan.query_required:
        raise InvalidArgumentsError(detail=f"missing required argument '{plan.query_param}'")

    limit = int(args.get("limit") or plan.limit_default)
    limit = max(1, min(limit, plan.limit_max))

    batch = await adapter.search(
        SearchRequest(
            collection=collection,
            vector=vector,
            mode="hybrid" if plan.mode == "hybrid" else "dense",
            query_text=str(query_text) if query_text else None,
            alpha=plan.alpha,
            filter_ir=ir,
            limit=limit,
            projection=plan.projection,
            with_score=plan.include_score,
        )
    )
    rows = batch.rows
    if plan.projection:
        projected = []
        missing = False
        for row in rows:
            item = {k: row.get(k) for k in plan.projection}
            if any(k not in row for k in plan.projection):
                missing = True
            if plan.include_score and "_score" in row:
                item["_score"] = row["_score"]
            if "_id" in row:
                item.setdefault("_id", row["_id"])
            projected.append(item)
        rows = projected
        if missing:
            warnings.append("VB4001")

    truncated = False
    encoded = json.dumps(rows, default=str).encode()
    while len(encoded) > MAX_BYTES and rows:
        rows = rows[:-1]
        truncated = True
        encoded = json.dumps(rows, default=str).encode()

    return ToolResult(
        rows=rows,
        count=len(rows),
        truncated=truncated,
        search_mode=search_mode if query_text else "none",
        warnings=warnings,
        compiled_query={"filter": native} if debug else None,
    )


# Cond re-export keeps static_conds typed for merge_and
_ = Cond
