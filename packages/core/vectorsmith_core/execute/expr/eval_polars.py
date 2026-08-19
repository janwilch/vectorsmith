"""Transpile expr AST to Polars expressions."""

from __future__ import annotations

from typing import Any

import polars as pl

from vectorsmith_core.errors import ExprError
from vectorsmith_core.execute.expr.parser import (
    Binary,
    ExprNode,
    Field,
    Literal,
    Param,
    Unary,
)


def eval_expr(
    node: ExprNode,
    df: pl.DataFrame,
    params: dict[str, Any],
) -> tuple[pl.Series, int]:
    """Return a boolean/value series and the count of null-in-comparison exclusions."""
    null_cmp = _NullCmp()
    expr = _to_pl(node, params, null_cmp)
    try:
        series = df.select(expr.alias("_vb")).to_series()
    except Exception as exc:  # noqa: BLE001
        raise ExprError(detail=f"expr evaluation failed: {exc}") from exc
    return series, null_cmp.count


class _NullCmp:
    count = 0


def _to_pl(node: ExprNode, params: dict[str, Any], null_cmp: _NullCmp) -> pl.Expr:
    if isinstance(node, Literal):
        return pl.lit(node.value)
    if isinstance(node, Field):
        return pl.col(node.path)
    if isinstance(node, Param):
        if node.name not in params:
            raise ExprError(detail=f"unknown param '{node.name}'")
        return pl.lit(params[node.name])
    if isinstance(node, Unary):
        child = _to_pl(node.child, params, null_cmp)  # type: ignore[arg-type]
        if node.op == "not":
            return ~child.fill_null(False)
        if node.op == "neg":
            return -child
        raise ExprError(detail=f"unknown unary op '{node.op}'")
    if isinstance(node, Binary):
        left = _to_pl(node.left, params, null_cmp)  # type: ignore[arg-type]
        right = _to_pl(node.right, params, null_cmp)  # type: ignore[arg-type]
        op = node.op
        if op == "and":
            return left.fill_null(False) & right.fill_null(False)
        if op == "or":
            return left.fill_null(False) | right.fill_null(False)
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return pl.when(right == 0).then(None).otherwise(left / right)
        if op in {"==", "!=", ">", ">=", "<", "<="}:
            if op in {">", ">=", "<", "<="}:
                # string cmp only ==/!= — numeric/bool otherwise
                pass
            both_null = left.is_null() | right.is_null()
            cmp = {
                "==": left == right,
                "!=": left != right,
                ">": left > right,
                ">=": left >= right,
                "<": left < right,
                "<=": left <= right,
            }[op]
            # null-in-cmp ⇒ row excluded (False) and counted
            return pl.when(both_null).then(pl.lit(False)).otherwise(cmp)
        raise ExprError(detail=f"unknown op '{op}'")
    raise ExprError(detail="unrecognized expr node")
