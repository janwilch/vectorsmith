"""T6: filter IR parse / bind / merge — property-tested binder rules."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given

from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.ir.filter import And, Cond, Or, ParamRef, bind, merge_and, parse_ir

eq = {"path": "status", "op": "eq", "value": "paid"}
rng = {"path": "amount", "op": "gte", "value": 10}


def test_empty_is_none() -> None:
    assert parse_ir(None) is None
    assert parse_ir({}) is None


def test_single_eq() -> None:
    n = parse_ir(eq)
    assert n == Cond("status", "eq", "paid")


def test_eq_range_and() -> None:
    n = parse_ir({"and": [eq, rng]})
    assert isinstance(n, And)
    assert len(n.children) == 2


def test_or_eq_eq() -> None:
    n = parse_ir({"or": [eq, {"path": "status", "op": "eq", "value": "overdue"}]})
    assert isinstance(n, Or)


def test_and_or_range() -> None:
    n = parse_ir({"and": [{"or": [eq, eq]}, rng]})
    assert isinstance(n, And)


def test_in_and_nin() -> None:
    assert parse_ir({"path": "id", "op": "in", "value": [1]}) == Cond("id", "in", [1])
    assert parse_ir({"path": "id", "op": "nin", "value": [1, 2]}) == Cond("id", "nin", [1, 2])


def test_param_ref_value() -> None:
    n = parse_ir({"path": "client", "op": "eq", "value": {"param": "client"}})
    assert isinstance(n, Cond)
    assert n.value == ParamRef("client")


def test_bind_optional_absent_prunes() -> None:
    n = parse_ir({"path": "client", "op": "eq", "value": {"param": "client"}})
    assert bind(n, {}) is None


def test_bind_required_absent_raises() -> None:
    n = parse_ir({"path": "client", "op": "eq", "value": {"param": "client"}})
    try:
        bind(n, {}, required=frozenset({"client"}))
    except InvalidArgumentsError:
        return
    raise AssertionError("expected InvalidArgumentsError")


def test_bind_substitutes() -> None:
    n = parse_ir({"path": "client", "op": "eq", "value": {"param": "client"}})
    assert bind(n, {"client": "Globex"}) == Cond("client", "eq", "Globex")


def test_one_child_or_collapses() -> None:
    n = parse_ir({"or": [eq, {"path": "x", "op": "eq", "value": {"param": "opt"}}]})
    bound = bind(n, {})
    assert bound == Cond("status", "eq", "paid")


def test_empty_and_after_prune_is_none() -> None:
    n = parse_ir({"and": [{"path": "a", "op": "eq", "value": {"param": "a"}}]})
    assert bind(n, {}) is None


def test_merge_and_static_and_param() -> None:
    static = parse_ir({"path": "tenant", "op": "eq", "value": "acme"})
    param = parse_ir({"path": "client", "op": "eq", "value": {"param": "client"}})
    merged = merge_and(static, bind(param, {"client": "Globex"}))
    assert isinstance(merged, And)
    assert len(merged.children) == 2


@given(st.lists(st.sampled_from(["a", "b", "c"]), max_size=5, unique=True))
def test_optional_absent_never_raises(names: list[str]) -> None:
    kids = [{"path": n, "op": "eq", "value": {"param": n}} for n in names]
    node = parse_ir({"and": kids} if kids else None)
    assert bind(node, {}) is None or isinstance(bind(node, {}), (Cond, And, Or))
