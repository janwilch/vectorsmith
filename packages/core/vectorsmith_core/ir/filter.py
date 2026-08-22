"""Filter IR: Cond / And / Or, parse, bind, merge_and."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from vectorsmith_core.errors import InvalidArgumentsError


@dataclass(frozen=True)
class ParamRef:
    name: str


@dataclass(frozen=True)
class Cond:
    path: str
    op: str
    value: object  # literal or ParamRef


@dataclass(frozen=True)
class And:
    children: tuple[IRNode, ...]


@dataclass(frozen=True)
class Or:
    children: tuple[IRNode, ...]


IRNode = Union[Cond, And, Or]


def parse_ir(data: object | None) -> IRNode | None:
    """Parse a filter dict into IR. ``None`` / ``{}`` → ``None``."""
    if data is None or data == {} or data == []:
        return None
    if not isinstance(data, dict):
        raise InvalidArgumentsError(detail="filter must be a mapping")
    if "and" in data:
        kids = tuple(n for n in (parse_ir(x) for x in data["and"]) if n is not None)
        return _collapse(And(kids))
    if "or" in data:
        kids = tuple(n for n in (parse_ir(x) for x in data["or"]) if n is not None)
        return _collapse(Or(kids))
    if "path" in data and "op" in data:
        raw = data.get("value", ParamRef(str(data["param"])) if "param" in data else None)
        value: object
        if isinstance(raw, dict) and ("param" in raw or "$param" in raw):
            value = ParamRef(str(raw.get("param") or raw.get("$param")))
        else:
            value = raw
        return Cond(path=str(data["path"]), op=str(data["op"]), value=value)
    raise InvalidArgumentsError(detail="unrecognized filter IR")


def _collapse(node: And | Or) -> IRNode | None:
    kids = node.children
    if len(kids) == 0:
        return None
    if len(kids) == 1:
        return kids[0]
    return node


def bind(
    node: IRNode | None,
    args: dict[str, Any],
    *,
    required: frozenset[str] = frozenset(),
) -> IRNode | None:
    """Substitute ParamRefs. Optional-absent prunes; required-absent raises."""
    if node is None:
        return None
    if isinstance(node, Cond):
        val = node.value
        if isinstance(val, ParamRef):
            if val.name in args and args[val.name] is not None:
                return Cond(node.path, node.op, args[val.name])
            if val.name in required:
                raise InvalidArgumentsError(detail=f"missing required argument '{val.name}'")
            return None
        return node
    kids = tuple(
        n for n in (bind(c, args, required=required) for c in node.children) if n is not None
    )
    if isinstance(node, And):
        return _collapse(And(kids))
    return _collapse(Or(kids))


def ir_paths(node: IRNode | None) -> set[str]:
    """Payload paths referenced by an IR tree (static + bound params)."""
    if node is None:
        return set()
    if isinstance(node, Cond):
        return {node.path}
    out: set[str] = set()
    for child in node.children:
        out |= ir_paths(child)
    return out


_INVERT_OP = {
    "eq": "ne",
    "ne": "eq",
    "gt": "lte",
    "gte": "lt",
    "lt": "gte",
    "lte": "gt",
    "in": "nin",
    "nin": "in",
}


def invert_cond(cond: Cond) -> Cond:
    """Logical NOT of an LCD condition (used for ``static_filters.must_not``)."""
    return Cond(cond.path, _INVERT_OP.get(cond.op, cond.op), cond.value)


def merge_and(*nodes: IRNode | None) -> IRNode | None:
    """AND-merge nodes, flattening nested Ands."""
    flat: list[IRNode] = []
    for n in nodes:
        if n is None:
            continue
        if isinstance(n, And):
            flat.extend(n.children)
        else:
            flat.append(n)
    return _collapse(And(tuple(flat)))
