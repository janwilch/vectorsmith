"""Collect-all TDS validator. Codes are stable (tech Appendix B)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from typing import Any, Literal

from vectorsmith_core.adapters.capabilities import CAPS_BY_BACKEND
from vectorsmith_core.tds.models import (
    PgvectorConn,
    QuerySpec,
    RetrieveStep,
    TDSFile,
    ToolSpec,
    is_table_mode,
)

RESERVED = frozenset(
    {
        "ping",
        "define_tool",
        "describe_collection",
        "list_available_tools",
        "run_tool",
        "list_my_connections",
        "get_started",
    }
)
TENANT_RE = re.compile(
    r"^(tenant|org(_id)?|organization_id|customer_id|account_id|workspace(_id)?)$"
)

DTYPE_OPS: dict[str, frozenset[str]] = {
    "keyword": frozenset({"eq", "ne", "in", "nin", "like", "text_match"}),
    "integer": frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"}),
    "float": frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"}),
    "datetime": frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"}),
    "boolean": frozenset({"eq", "ne"}),
    "keyword[]": frozenset({"in", "nin", "contains_any", "contains_all"}),
    "unknown": frozenset(),
}

GATED_OPS = frozenset({"exists", "is_null", "contains_any", "contains_all", "like", "text_match"})


def _issue(
    code: str,
    message: str,
    *,
    severity: Literal["error", "warning"] = "error",
    tool: str | None = None,
    path: str | None = None,
) -> Any:
    from vectorsmith_core.api import Issue

    return Issue(severity=severity, code=code, message=message, tool=tool, path=path)


def _enabled_builtin_names(tds: TDSFile) -> set[str]:
    names: set[str] = set()
    for cname, conn in tds.connections.items():
        bt = conn.builtin_tools
        if bt.semantic_search:
            names.add(f"search_{cname}")
        if bt.get_by_id:
            names.add(f"get_{cname}_by_id")
        if bt.count:
            names.add(f"count_{cname}")
        if bt.list_collections:
            names.add(f"list_{cname}_collections")
    return names


def validate(tds: TDSFile, *, live_sparse: dict[str, bool] | None = None) -> list[Any]:
    """Return all issues. ``live_sparse`` maps ``connection.collection`` → has_sparse."""
    issues: list[Any] = []
    reserved = RESERVED | _enabled_builtin_names(tds)
    seen_params: dict[str, set[str]] = {}

    for tool in tds.tools:
        issues.extend(_validate_tool(tds, tool, reserved, live_sparse))
        names = [p.name for p in tool.parameters]
        if len(names) != len(set(names)):
            issues.append(_issue("VB2002", "duplicate parameter names", tool=tool.name))
        seen_params[tool.name] = set(names)

    issues.extend(_builtin_lints(tds))
    return issues


def _conn_for(tds: TDSFile, tool: ToolSpec) -> object | None:
    if tool.target:
        return tds.connections.get(tool.target.connection)
    for step in tool.steps or []:
        if isinstance(step, RetrieveStep):
            return tds.connections.get(step.retrieve.target.connection)
    return None


def _validate_tool(
    tds: TDSFile,
    tool: ToolSpec,
    reserved: AbstractSet[str],
    live_sparse: dict[str, bool] | None,
) -> list[Any]:
    issues: list[Any] = []
    if tool.name in reserved and not tool._synthetic:
        issues.append(_issue("VB2010", f"name '{tool.name}' is reserved", tool=tool.name))
    if tool.kind == "meta" and not tool._synthetic:
        issues.append(_issue("VB2014", "user files may not declare kind=meta", tool=tool.name))
    if tool.kind == "meta" and (tool.query or tool.parameters or tool.static_filters):
        issues.append(
            _issue("VB2011", "meta tools cannot have query/params/filters", tool=tool.name)
        )

    conn = _conn_for(tds, tool)
    caps = CAPS_BY_BACKEND.get(getattr(conn, "backend", ""), None)

    if isinstance(conn, PgvectorConn) and is_table_mode(conn):
        if tool.kind == "search" or tool.query is not None:
            issues.append(
                _issue(
                    "VB2016",
                    "this connection has no vector column — table mode supports "
                    "lookup/count/scroll/pipeline",
                    tool=tool.name,
                )
            )

    if tool.kind == "lookup" and tool.output.limit_default != 1:
        issues.append(
            _issue("VB2006", "lookup limit forced to 1", severity="warning", tool=tool.name)
        )

    if tool.target and not isinstance(tool.target.collection, str) and not tool._synthetic:
        issues.append(_issue("VB2015", "ParamRef targets are synthesis-only", tool=tool.name))

    for p in tool.parameters:
        allowed = DTYPE_OPS.get(str(p.dtype), frozenset())
        if p.op and p.op not in allowed:
            issues.append(
                _issue(
                    "VB2001",
                    f"op '{p.op}' is not valid for dtype '{p.dtype}'",
                    tool=tool.name,
                    path=p.path,
                )
            )
        if p.op and caps and p.op in GATED_OPS and p.op not in caps.ops:
            issues.append(
                _issue(
                    "VB2004",
                    f"backend does not support op '{p.op}'",
                    tool=tool.name,
                    path=p.path,
                )
            )
        if p.enum and p.op not in {None, "eq", "ne", "in", "nin"}:
            issues.append(
                _issue(
                    "VB2005",
                    "enum is unusual with this operator",
                    severity="warning",
                    tool=tool.name,
                    path=p.path,
                )
            )
        if p.path and p.path.count(".") >= 1 and caps and not caps.nested_paths:
            issues.append(
                _issue(
                    "VB2004", "backend does not support nested paths", tool=tool.name, path=p.path
                )
            )

    queries: list[QuerySpec] = []
    if tool.query:
        queries.append(tool.query)
    for step in tool.steps or []:
        if isinstance(step, RetrieveStep) and step.retrieve.query:
            queries.append(step.retrieve.query)
    for q in queries:
        if q.mode == "hybrid":
            if caps is None or not caps.hybrid:
                issues.append(
                    _issue("VB2012", "hybrid is not supported on this backend", tool=tool.name)
                )
            elif live_sparse is not None and conn is not None:
                coll = (
                    tool.target.collection
                    if tool.target and isinstance(tool.target.collection, str)
                    else ""
                )
                # if we have live knowledge and sparse is False → error
                if any(k.endswith(f":{coll}") and not v for k, v in live_sparse.items()):
                    issues.append(
                        _issue(
                            "VB2013",
                            "hybrid requires collection sparse vector config",
                            tool=tool.name,
                        )
                    )
            elif live_sparse is None:
                issues.append(
                    _issue(
                        "VB2013",
                        "hybrid requires collection sparse vector config (confirm with --live)",
                        severity="warning",
                        tool=tool.name,
                    )
                )

    if tool.kind == "pipeline":
        if not tool.steps or not isinstance(tool.steps[0], RetrieveStep):
            issues.append(_issue("VB2101", "pipeline must start with retrieve", tool=tool.name))
        for step in tool.steps or []:
            if hasattr(step, "post_filter"):
                expr = step.post_filter.expr
                if not expr or not expr.strip():
                    issues.append(_issue("VB2102", "empty post_filter expr", tool=tool.name))

    desc = tool.description.strip()
    if desc.lower().replace("_", " ") == tool.name.replace("_", " "):
        issues.append(
            _issue(
                "VB3002",
                "description is too close to the tool name",
                severity="warning",
                tool=tool.name,
            )
        )
    if len(desc) < 40:
        issues.append(
            _issue(
                "VB3001",
                "description should tell Claude when to pick this tool",
                severity="warning",
                tool=tool.name,
            )
        )
    return issues


def _builtin_lints(tds: TDSFile) -> list[Any]:
    issues: list[Any] = []
    user_search = {t.name for t in tds.tools if t.kind == "search" and not t._synthetic}
    for cname, conn in tds.connections.items():
        if not conn.builtin_tools.semantic_search:
            continue
        bname = f"search_{cname}"
        if user_search:
            issues.append(
                _issue(
                    "VB3003",
                    f"unrestricted built-in {bname} may overlap user search tools",
                    severity="warning",
                    tool=bname,
                )
            )
        bd = conn.builtin_defaults
        if not bd.static_filters and (bd.collections is None or len(bd.collections) != 1):
            # heuristic: we cannot see payload fields here; warn if names look tenant-ish
            # near-miss fixtures must not trigger — only exact reserved field names in defaults
            for sf in bd.static_filters:
                if TENANT_RE.match(sf.path):
                    break
            else:
                issues.append(
                    _issue(
                        "VB3004",
                        "unrestricted semantic_search without tenant static filters",
                        severity="warning",
                        tool=bname,
                    )
                )
        if bd.descriptions:
            for key, text in bd.descriptions.items():
                if len(text) < 20:
                    issues.append(
                        _issue(
                            "VB3005",
                            f"built-in description override for {key} is too short",
                            severity="warning",
                            tool=f"{key}_{cname}",
                        )
                    )
    return issues


_SKIP_PATHS = frozenset({"id", "_id", "_score"})


def embedding_dim(model: str) -> int | None:
    """Known FastEmbed model size, or None if the id is not in the registry."""
    from vectorsmith_core.embed.models import DIMS

    if model in DIMS:
        return DIMS[model]
    return DIMS.get(model.split("/", 1)[-1])


def live_contract_issues(
    tds: TDSFile,
    plans: Mapping[str, Any],
    native: Mapping[str, Mapping[str, Any]],
) -> list[Any]:
    """Embedding dim + payload-path checks using live introspect (``validate --live``).

    ``plans`` maps tool name → ``ExecutionPlan``. ``native`` maps
    ``connection:collection`` → ``{dim, fields, sparse}``.
    """
    from vectorsmith_core.compilepkg.compiler import ExecutionPlan
    from vectorsmith_core.ir.filter import ir_paths

    issues: list[Any] = []
    default_model = tds.defaults.embedding
    for name, plan in plans.items():
        if not isinstance(plan, ExecutionPlan):
            continue
        coll = plan.collection if isinstance(plan.collection, str) else None
        if not plan.connection or not coll:
            continue
        key = f"{plan.connection}:{coll}"
        info = native.get(key)
        if not info:
            continue
        model = plan.embedding or default_model
        if plan.kind in {"search", "pipeline"}:
            dim = embedding_dim(model)
            live_dim = info.get("dim")
            if dim is None:
                issues.append(
                    _issue(
                        "VB2018",
                        f"unknown embedding model '{model}' — cannot check collection dim",
                        severity="warning",
                        tool=name,
                    )
                )
            elif isinstance(live_dim, int) and live_dim != dim:
                issues.append(
                    _issue(
                        "VB2017",
                        f"collection dim {live_dim} != embedder '{model}' ({dim})",
                        tool=name,
                        path=coll,
                    )
                )
        fields = info.get("fields")
        if not isinstance(fields, list) or not fields:
            continue
        field_set = {str(f) for f in fields}
        wanted: set[str] = set()
        for cond in plan.static_conds:
            wanted |= ir_paths(cond)
        for cond in plan.param_conds:
            wanted |= ir_paths(cond)
        wanted |= {p for p in (plan.projection or []) if p}
        for path in sorted(wanted - _SKIP_PATHS):
            head = path.split(".", 1)[0]
            if path not in field_set and head not in field_set:
                issues.append(
                    _issue(
                        "VB4004",
                        f"payload path '{path}' was not seen on collection '{coll}'",
                        severity="warning",
                        tool=name,
                        path=path,
                    )
                )
    return issues
