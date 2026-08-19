"""Constrained expression language (Lark → Polars)."""

from vectorsmith_core.execute.expr.eval_polars import eval_expr
from vectorsmith_core.execute.expr.parser import expr_fields, parse_expr

__all__ = ["eval_expr", "expr_fields", "parse_expr"]
