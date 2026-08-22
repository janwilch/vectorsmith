"""Shared MCP tool listing/calling for stdio and HTTP."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from vectorsmith_core.api import CallContext, Project, draft_tool
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.observe.audit import build_audit_event
from vectorsmith_core.security.rbac import check_rbac

_AUDIT_LOG = logging.getLogger("vectorsmith.audit")
_CALL_LOG = logging.getLogger("vectorsmith.call")
_META_AUDIT = frozenset({"list_available_tools", "run_tool"})

DEFINE_DESC = (
    "Propose a new read-only tool from describe_collection fields only. "
    "Call describe_collection FIRST. Server saves a draft; the user must "
    "run `vectorsmith approve NAME` — this never writes tools.yaml."
)
DESCRIBE_DESC = (
    "Return introspected fields for a collection so define_tool can be grounded."
)
LIVE_CATALOG_DESC = (
    "Live VectorSmith catalog from the current tools.yaml, including tools "
    "saved after this chat started. Claude Desktop freezes the named connector "
    "list at connect — call this before saying a tool is missing, then invoke "
    "with run_tool."
)
LIVE_RUN_DESC = (
    "Run any VectorSmith tool by name with its arguments from "
    "list_available_tools. Use this for tools added to tools.yaml after Claude "
    "connected; Desktop will not show those names in the connector list. "
    "Arguments are re-validated against that tool's compiled inputSchema "
    "(types, enums, limits); hidden static_filters and request tenancy still apply. "
    "Not a bypass."
)
SERVER_INSTRUCTIONS = (
    "VectorSmith reloads tools.yaml while you stay connected. Claude Desktop "
    "freezes the named tool list at connect. Call list_available_tools for the "
    "live catalog, then run_tool to invoke tools that are not in your original list."
)
SERVER_INSTRUCTIONS_NO_META = (
    "VectorSmith compiled tools from tools.yaml. Call tools by their advertised "
    "names. Stdio --watch recompiles on save; hosts that freeze tools/list still "
    "need a reconnect to see new names."
)
META_TOOLS = frozenset({"list_available_tools", "run_tool"})


def server_instructions(*, include_meta: bool = True) -> str:
    return SERVER_INSTRUCTIONS if include_meta else SERVER_INSTRUCTIONS_NO_META


def authoring_enabled(project: Project, enable_define: bool) -> bool:
    return enable_define or bool(project.tds.authoring.define_tool)


def mcp_schemas(
    project: Project,
    *,
    enable_define: bool,
    include_meta: bool = True,
) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    if include_meta:
        schemas.extend(
            [
                {
                    "name": "list_available_tools",
                    "description": LIVE_CATALOG_DESC,
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "run_tool",
                    "description": LIVE_RUN_DESC,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Tool name from list_available_tools",
                            },
                            "arguments": {
                                "type": "object",
                                "additionalProperties": True,
                                "description": (
                                    "Arguments for the named tool. Validated against "
                                    "that tool's compiled inputSchema, not this envelope."
                                ),
                            },
                        },
                        "required": ["name"],
                    },
                },
            ]
        )
    schemas.extend(project.mcp_tool_schemas())
    if authoring_enabled(project, enable_define):
        schemas.append(
            {
                "name": "describe_collection",
                "description": DESCRIBE_DESC,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "connection": {"type": "string"},
                        "collection": {"type": "string"},
                    },
                    "required": ["connection", "collection"],
                },
            }
        )
        schemas.append(
            {
                "name": "define_tool",
                "description": DEFINE_DESC,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "spec": {"type": "object"},
                    },
                    "required": ["name", "description", "spec"],
                },
            }
        )
    return schemas


async def dispatch(
    engine: Engine,
    name: str,
    args: dict[str, Any],
    *,
    ctx: CallContext,
    enable_define: bool,
    drafts_path: Path,
    include_meta: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await _dispatch_inner(
            engine,
            name,
            args,
            ctx=ctx,
            enable_define=enable_define,
            drafts_path=drafts_path,
            include_meta=include_meta,
        )
    except Exception as exc:
        await _emit_audit(engine, ctx, name, args, started, error=exc)
        raise
    await _emit_audit(engine, ctx, name, args, started, result=result)
    _CALL_LOG.info(
        "tool call completed",
        extra={
            "request_id": ctx.request_id,
            "principal": ctx.principal,
            "tool": name,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return result


async def _dispatch_inner(
    engine: Engine,
    name: str,
    args: dict[str, Any],
    *,
    ctx: CallContext,
    enable_define: bool,
    drafts_path: Path,
    include_meta: bool = True,
) -> dict[str, Any]:
    rbac = engine.project.tds.security.rbac
    check_rbac(ctx, name, rbac, allow_meta=include_meta)
    if include_meta and name == "list_available_tools":
        return _list_available(
            engine.project, enable_define=enable_define, include_meta=include_meta
        )
    if include_meta and name == "run_tool":
        return await _run_named(
            engine,
            args,
            ctx=ctx,
            enable_define=enable_define,
            drafts_path=drafts_path,
            include_meta=include_meta,
        )
    if name == "describe_collection" and authoring_enabled(engine.project, enable_define):
        report = await engine.introspect(
            str(args["connection"]), collections=[str(args["collection"])]
        )
        cols = report.get("collections") or []
        fields = cols[0].get("fields") if cols else []
        return {"rows": fields, "count": len(fields)}
    if name == "define_tool" and authoring_enabled(engine.project, enable_define):
        return _define_tool(engine.project, args, drafts_path)
    result = await engine.call(name, args, ctx=ctx)
    return result.model_dump()


async def _emit_audit(
    engine: Engine,
    ctx: CallContext,
    name: str,
    args: dict[str, Any],
    started: float,
    *,
    result: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> None:
    sink = getattr(engine, "audit_sink", None)
    cfg = engine.project.tds.observability.audit
    if sink is None:
        return
    if name in _META_AUDIT or name in cfg.exclude_tools:
        return
    compiled = engine.project.tools.get(name)
    plan = compiled.plan if compiled is not None else None
    event = build_audit_event(
        cfg=cfg,
        ctx=ctx,
        tool=name,
        args=args,
        connection=getattr(plan, "connection", None),
        collection=getattr(plan, "collection", None),
        latency_ms=int((time.perf_counter() - started) * 1000),
        result=result,
        error=error,
    )
    try:
        await sink.emit(event)
    except Exception:
        _AUDIT_LOG.warning("audit emit failed", exc_info=True)


def _list_available(
    project: Project, *, enable_define: bool, include_meta: bool = True
) -> dict[str, Any]:
    rows = [
        {
            "name": schema["name"],
            "description": schema.get("description"),
            "inputSchema": schema.get("inputSchema"),
        }
        for schema in mcp_schemas(
            project, enable_define=enable_define, include_meta=include_meta
        )
        if schema["name"] not in META_TOOLS
    ]
    return {
        "rows": rows,
        "count": len(rows),
        "message": (
            "Live catalog after any tools.yaml reload. Call run_tool with "
            "name + arguments for tools missing from the original connector list."
        ),
    }


async def _run_named(
    engine: Engine,
    args: dict[str, Any],
    *,
    ctx: CallContext,
    enable_define: bool,
    drafts_path: Path,
    include_meta: bool = True,
) -> dict[str, Any]:
    inner = str(args.get("name") or "").strip()
    if not inner:
        return {"rows": [], "count": 0, "message": "run_tool requires name."}
    if inner == "run_tool":
        return {"rows": [], "count": 0, "message": "run_tool cannot call itself."}
    inner_args = args.get("arguments")
    if inner_args is None:
        inner_args = {}
    if isinstance(inner_args, str):
        inner_args = json.loads(inner_args) if inner_args.strip() else {}
    if not isinstance(inner_args, dict):
        return {
            "rows": [],
            "count": 0,
            "message": "run_tool arguments must be an object (or JSON object string).",
        }
    check_rbac(ctx, inner, engine.project.tds.security.rbac)
    return await dispatch(
        engine,
        inner,
        inner_args,
        ctx=ctx,
        enable_define=enable_define,
        drafts_path=drafts_path,
        include_meta=include_meta,
    )


def expire_old_drafts(path: Path) -> None:
    if not path.exists():
        return
    data = yaml.safe_load(path.read_text()) or {}
    drafts = data.get("drafts") or []
    cutoff = datetime.now(UTC) - timedelta(days=30)
    changed = False
    for d in drafts:
        if d.get("status") != "pending":
            continue
        created = d.get("created_at") or d.get("provenance", {}).get("created_at")
        if not created:
            continue
        try:
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts < cutoff:
            d["status"] = "expired"
            changed = True
    if changed:
        path.write_text(yaml.safe_dump(data, sort_keys=False))


def _define_tool(project: Project, args: dict[str, Any], path: Path) -> dict[str, Any]:
    expire_old_drafts(path)
    data: dict[str, Any] = {"drafts": []}
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {"drafts": []}
        data.setdefault("drafts", [])
    pending = [d for d in data["drafts"] if d.get("status") == "pending"]
    if len(pending) >= 10:
        return {
            "rows": [],
            "count": 0,
            "warnings": ["draft cap: 10 pending drafts — reject or approve first"],
            "message": "Draft cap reached (10 pending). Reject or approve existing drafts.",
        }
    spec = dict(args.get("spec") or {})
    spec.setdefault("name", args.get("name"))
    spec.setdefault("description", args.get("description"))
    draft = draft_tool(
        project,
        {
            "created_by": "define_tool",
            "created_at": datetime.now(UTC).isoformat(),
            "conversation_hint": args.get("description"),
        },
        spec,
    )
    errors = [i for i in draft.validator_issues if i.severity == "error"]
    block = {
        "status": draft.status,
        "created_at": draft.provenance.get("created_at"),
        "hash": draft.provenance.get("hash"),
        "tool": json.loads(draft.spec.model_dump_json()),
        "issues": [i.model_dump() for i in draft.validator_issues],
    }
    if errors:
        return {
            "rows": [i.model_dump() for i in errors],
            "count": len(errors),
            "message": "Draft has errors; fix and call define_tool again.",
        }
    data["drafts"].append(block)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    n_warn = sum(1 for i in draft.validator_issues if i.severity == "warning")
    return {
        "rows": [],
        "count": 0,
        "warnings": [i.code for i in draft.validator_issues if i.severity == "warning"],
        "message": (
            f"Draft `{draft.spec.name}` saved with {n_warn} warning(s). "
            f"Run `vectorsmith approve {draft.spec.name}`, then call "
            "list_available_tools (Claude Desktop will not refresh named connector tools)."
        ),
    }
