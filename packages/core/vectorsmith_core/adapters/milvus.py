"""Milvus adapter."""

from __future__ import annotations

from typing import Any, ClassVar

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import MILVUS_CAPS
from vectorsmith_core.errors import BackendUnreachable
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or


class MilvusAdapter(VectorBackendAdapter):
    caps: ClassVar = MILVUS_CAPS

    def __init__(self, creds: dict[str, str]) -> None:
        self.uri = creds.get("uri", "")
        self.token = creds.get("token")
        self.user = creds.get("user")
        self.password = creds.get("password")
        self.database = creds.get("database") or "default"
        self._connected = False

    def compile_filter(self, node: IRNode | None) -> object:
        if node is None:
            return ""
        if isinstance(node, Cond):
            val = node.value
            if isinstance(val, str):
                lit = "'" + val.replace("'", "''") + "'"
            elif isinstance(val, list):
                inner = ", ".join(
                    "'" + str(x).replace("'", "''") + "'" if isinstance(x, str) else str(x)
                    for x in val
                )
                lit = f"[{inner}]"
            else:
                lit = repr(val)
            ops = {
                "eq": "==",
                "ne": "!=",
                "gt": ">",
                "gte": ">=",
                "lt": "<",
                "lte": "<=",
                "in": "in",
                "nin": "not in",
            }
            op = ops.get(node.op, node.op)
            return f"{node.path} {op} {lit}"
        if isinstance(node, And):
            return " and ".join(f"({self.compile_filter(c)})" for c in node.children)
        if isinstance(node, Or):
            return " or ".join(f"({self.compile_filter(c)})" for c in node.children)
        return ""

    def _sdk(self) -> Any:
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise BackendUnreachable(
                detail="milvus extra not installed: pip install vectorsmith-core[milvus]"
            ) from exc
        kwargs: dict[str, Any] = {"uri": self.uri, "db_name": self.database}
        if self.token:
            kwargs["token"] = self.token
        if self.user:
            kwargs["user"] = self.user
            kwargs["password"] = self.password
        return MilvusClient(**kwargs)

    async def health(self) -> bool:
        try:
            self._sdk().list_collections()
            return True
        except BackendUnreachable:
            raise
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def list_collections(self) -> list[str]:
        return list(self._sdk().list_collections())

    async def search(self, req: SearchRequest) -> RowBatch:
        if req.vector is None:
            return RowBatch(rows=[], exhausted=True)
        expr = self.compile_filter(
            req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else None
        )
        try:
            hits = self._sdk().search(
                collection_name=req.collection,
                data=[req.vector],
                limit=req.limit,
                filter=expr or "",
                output_fields=list(req.projection) if req.projection else ["*"],
            )
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc
        rows = []
        first = hits[0] if hits else []
        for h in first:
            entity = dict(h.get("entity") or h)
            entity["_id"] = h.get("id")
            entity["_score"] = h.get("distance")
            rows.append(entity)
        return RowBatch(rows=rows, exhausted=True)

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        expr = self.compile_filter(filter_ir)
        try:
            rows = self._sdk().query(
                collection_name=collection,
                filter=expr or "",
                output_fields=["count(*)"],
            )
            return int(rows or 0) or 0
        except Exception:
            stats = self._sdk().get_collection_stats(collection)
            return int(stats.get("row_count", 0) if isinstance(stats, dict) else 0)

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        try:
            rows = self._sdk().query(
                collection_name=collection, filter="", limit=n, output_fields=["*"]
            )
            return [dict(r) for r in rows or []]
        except Exception:
            return []
