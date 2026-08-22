"""Pipeline execution with widening and honest incompleteness."""

from __future__ import annotations

from typing import Any

import polars as pl

from vectorsmith_core.api import CompiledTool, ToolResult
from vectorsmith_core.compilepkg.compiler import ExecutionPlan
from vectorsmith_core.errors import ExprError, SchemaDriftError
from vectorsmith_core.execute.expr.eval_polars import eval_expr
from vectorsmith_core.execute.expr.parser import expr_fields, parse_expr
from vectorsmith_core.execute.single_step import execute_single
from vectorsmith_core.tds.models import (
    GroupByStep,
    PostFilterStep,
    ProjectStep,
    SortStep,
)


async def execute_pipeline(
    compiled: CompiledTool,
    plan: ExecutionPlan,
    args: dict[str, Any],
    **kwargs: Any,
) -> ToolResult:
    """Retrieve with overfetch, then apply remaining steps in-process."""
    requested = int(args.get(plan.fetch_k_param) or plan.limit_default)
    k = min(max(requested, 1) * plan.overfetch_factor, plan.max_candidates)
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    exhausted = False
    attempts = 0
    cur_k = k
    result: ToolResult | None = None
    while attempts < 3:
        widened = dict(args)
        widened["limit"] = cur_k
        result = await execute_single(compiled, plan, widened, **kwargs)
        rows = list(result.rows)
        exhausted = True
        warnings.extend(result.warnings)
        if len(rows) >= requested or cur_k >= plan.max_candidates:
            break
        cur_k = min(cur_k * 3, plan.max_candidates)
        attempts += 1

    steps = plan.steps or []
    df = pl.DataFrame(rows) if rows else pl.DataFrame()
    if rows:
        df, drift_warn = _cast_expr_columns(df, steps)
        warnings.extend(drift_warn)

    from vectorsmith_core.observe.tracing import start_span

    for step in steps[1:]:
        with start_span("vectorsmith.pipeline.step", step_kind=type(step).__name__):
            if isinstance(step, PostFilterStep):
                if df.is_empty():
                    continue
                ast = parse_expr(step.post_filter.expr)
                series, null_cmp = eval_expr(ast, df, args)
                if series.dtype != pl.Boolean:
                    series = series.cast(pl.Boolean, strict=False).fill_null(False)
                df = df.filter(series)
                if null_cmp:
                    warnings.append("VB4002")
            elif isinstance(step, GroupByStep):
                df = _group_by(df, step, args)
            elif isinstance(step, SortStep):
                if step.sort.by in df.columns:
                    df = df.sort(step.sort.by, descending=step.sort.desc)
            elif isinstance(step, ProjectStep):
                keep = [c for c in step.project.fields if c in df.columns]
                if keep:
                    df = df.select(keep)

    out_rows = df.to_dicts() if not df.is_empty() else []
    incomplete = len(out_rows) < requested and not exhausted and cur_k >= plan.max_candidates
    out_rows = out_rows[:requested]
    mode = result.search_mode if result is not None else "none"
    return ToolResult(
        rows=out_rows,
        count=len(out_rows),
        may_be_incomplete=incomplete,
        warnings=warnings,
        search_mode=mode,
    )


def _cast_expr_columns(
    df: pl.DataFrame, steps: list[object]
) -> tuple[pl.DataFrame, list[str]]:
    fields: set[str] = set()
    for step in steps:
        if isinstance(step, PostFilterStep):
            try:
                fields |= expr_fields(parse_expr(step.post_filter.expr))
            except ExprError:
                continue
    warnings: list[str] = []
    if not fields:
        return df, warnings
    n = df.height or 1
    for path in fields:
        if path not in df.columns:
            continue
        col = df.get_column(path)
        if col.dtype == pl.Utf8:
            casted = col.cast(pl.Float64, strict=False)
            extra_nulls = casted.null_count() - col.null_count()
            if extra_nulls / n > 0.05:
                raise SchemaDriftError(
                    detail=f"more than 5% of values in '{path}' failed to cast"
                )
            df = df.with_columns(casted.alias(path))
    return df, warnings


def _group_by(df: pl.DataFrame, step: GroupByStep, args: dict[str, Any]) -> pl.DataFrame:
    if df.is_empty():
        return df
    keys = [k for k in step.group_by.keys if k in df.columns]
    if not keys:
        return df
    pg = step.group_by.per_group
    take = 3
    if pg is not None:
        raw = pg.take
        if isinstance(raw, str) and raw.startswith("params."):
            name = raw.split(".", 1)[1]
            take = int(args.get(name) or 3)
        else:
            take = int(raw)
        take = max(1, take)
        sort_by = pg.sort_by if pg.sort_by in df.columns else None
        if sort_by:
            df = df.sort(sort_by, descending=pg.desc)
    parts: list[pl.DataFrame] = []
    for _, part in df.group_by(keys, maintain_order=True):
        parts.append(part.head(take))
    if not parts:
        return df.head(0)
    return pl.concat(parts)
