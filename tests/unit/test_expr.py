"""T13: expr parser and polars eval."""

from __future__ import annotations

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vectorsmith_core.errors import ExprError
from vectorsmith_core.execute.expr.eval_polars import eval_expr
from vectorsmith_core.execute.expr.parser import parse_expr


def test_parse_compare_and_params() -> None:
    ast = parse_expr("amount > paid_amount AND days_overdue >= params.min_days")
    assert ast is not None


def test_eval_filters_rows() -> None:
    df = pl.DataFrame({"amount": [10, 3], "paid_amount": [1, 4], "days_overdue": [5, 0]})
    ast = parse_expr("amount > paid_amount AND days_overdue >= params.min_days")
    series, _ = eval_expr(ast, df, {"min_days": 1})
    assert series.to_list() == [True, False]


def test_div_zero_is_null() -> None:
    df = pl.DataFrame({"a": [1], "b": [0]})
    ast = parse_expr("a / b")
    series, _ = eval_expr(ast, df, {})
    assert series.to_list() == [None]


def test_null_compare_excludes() -> None:
    df = pl.DataFrame({"a": [1, None], "b": [1, 1]})
    ast = parse_expr("a == b")
    series, _ = eval_expr(ast, df, {})
    assert series.to_list() == [True, False]


def test_bad_expr_is_expr_error() -> None:
    with pytest.raises(ExprError):
        parse_expr("amount >")


@settings(max_examples=40, deadline=None)
@given(st.text(max_size=40))
def test_garbage_only_expr_error(text: str) -> None:
    try:
        parse_expr(text)
    except ExprError:
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"non-ExprError escaped: {type(exc)}") from exc
