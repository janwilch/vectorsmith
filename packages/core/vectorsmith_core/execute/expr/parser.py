"""Lark parser for the expr language. Only ``ExprError`` escapes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import LarkError

from vectorsmith_core.errors import ExprError

_GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()
_PARSER = Lark(_GRAMMAR, parser="lalr", maybe_placeholders=False)


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class Field:
    path: str


@dataclass(frozen=True)
class Param:
    name: str


@dataclass(frozen=True)
class Unary:
    op: str
    child: object


@dataclass(frozen=True)
class Binary:
    op: str
    left: object
    right: object


ExprNode = Literal | Field | Param | Unary | Binary


@v_args(inline=True)
class _ToAst(Transformer[Token, ExprNode]):
    def number(self, tok: Token) -> Literal:
        text = str(tok)
        if "." in text or "e" in text.lower():
            return Literal(float(text))
        return Literal(int(text))

    def string(self, tok: Token) -> Literal:
        raw = str(tok)
        return Literal(bytes(raw[1:-1], "utf-8").decode("unicode_escape"))

    def true_(self) -> Literal:
        return Literal(True)

    def false_(self) -> Literal:
        return Literal(False)

    def null_(self) -> Literal:
        return Literal(None)

    def field(self, *parts: Token) -> Field:
        return Field(".".join(str(p) for p in parts))

    def param(self, name: Token) -> Param:
        return Param(str(name))

    def not_(self, child: ExprNode) -> Unary:
        return Unary("not", child)

    def neg(self, child: ExprNode) -> Unary:
        return Unary("neg", child)

    def cmp(self, left: ExprNode, op: Token, right: ExprNode) -> Binary:
        return Binary(str(op), left, right)

    def arith(self, first: ExprNode, *rest: object) -> ExprNode:
        node: ExprNode = first
        i = 0
        while i < len(rest):
            op = str(rest[i])
            node = Binary(op, node, rest[i + 1])
            i += 2
        return node

    def term(self, first: ExprNode, *rest: object) -> ExprNode:
        return self.arith(first, *rest)

    def and_expr(self, first: ExprNode, *rest: ExprNode) -> ExprNode:
        node: ExprNode = first
        for child in rest:
            node = Binary("and", node, child)
        return node

    def or_expr(self, first: ExprNode, *rest: ExprNode) -> ExprNode:
        node: ExprNode = first
        for child in rest:
            node = Binary("or", node, child)
        return node

    def expr(self, node: ExprNode) -> ExprNode:
        return node

    def start(self, node: ExprNode) -> ExprNode:
        return node


def parse_expr(text: str) -> ExprNode:
    """Parse ``expr`` source. Garbage and syntax errors become ``ExprError``."""
    try:
        tree = _PARSER.parse(text)
        ast = _ToAst().transform(tree)
    except (LarkError, ValueError, TypeError, RecursionError) as exc:
        raise ExprError(detail=f"invalid expr: {exc}") from exc
    except ExprError:
        raise
    except Exception as exc:  # noqa: BLE001 — firewall: only ExprError escapes
        raise ExprError(detail=f"invalid expr: {exc}") from exc
    return ast


def expr_fields(node: ExprNode) -> set[str]:
    if isinstance(node, Field):
        return {node.path}
    if isinstance(node, Unary):
        return expr_fields(node.child)  # type: ignore[arg-type]
    if isinstance(node, Binary):
        return expr_fields(node.left) | expr_fields(node.right)  # type: ignore[arg-type]
    return set()


def _fold_and_or(items: list[Any], op: str) -> ExprNode:
    node: ExprNode = items[0]
    for child in items[1:]:
        node = Binary(op, node, child)
    return node
