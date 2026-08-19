"""Pinecone adapter — one connection = one index; collection = namespace."""

from __future__ import annotations

from typing import Any, ClassVar

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import PINECONE_CAPS
from vectorsmith_core.errors import BackendUnreachable
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or


class PineconeAdapter(VectorBackendAdapter):
    caps: ClassVar = PINECONE_CAPS

    def __init__(self, creds: dict[str, str]) -> None:
        self.api_key = creds.get("api_key", "")
        self.host = creds.get("host", "")
        self.namespace = creds.get("namespace")
        self._index: Any = None

    def compile_filter(self, node: IRNode | None) -> object:
        if node is None:
            return None
        if isinstance(node, Cond):
            if "." in node.path:
                raise BackendUnreachable(detail="VB2004 nested paths not supported")
            values = node.value
            if node.op == "in" and isinstance(values, list) and len(values) > 10_000:
                values = values[:10_000]
            return {node.path: {f"${node.op}": values}}
        if isinstance(node, And):
            return {"$and": [self.compile_filter(c) for c in node.children]}
        if isinstance(node, Or):
            return {"$or": [self.compile_filter(c) for c in node.children]}
        return None

    def _sdk(self) -> Any:
        if self._index is not None:
            return self._index
        try:
            from pinecone import Pinecone  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendUnreachable(
                detail="pinecone extra not installed: pip install vectorsmith-core[pinecone]"
            ) from exc
        self._index = Pinecone(api_key=self.api_key).Index(host=self.host)
        return self._index

    async def health(self) -> bool:
        try:
            self._sdk().describe_index_stats()
            return True
        except BackendUnreachable:
            raise
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def list_collections(self) -> list[str]:
        stats = self._sdk().describe_index_stats()
        nss = getattr(stats, "namespaces", None) or {}
        if isinstance(nss, dict):
            return list(nss) or [""]
        return [""]

    async def search(self, req: SearchRequest) -> RowBatch:
        if req.vector is None:
            return RowBatch(rows=[], exhausted=True)
        ns = req.collection if req.collection != "__param__" else (self.namespace or "")
        try:
            res = self._sdk().query(
                vector=req.vector,
                top_k=req.limit,
                namespace=ns,
                filter=self.compile_filter(
                    req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else None
                ),
                include_metadata=True,
            )
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc
        matches = getattr(res, "matches", None) or res.get("matches", [])
        rows = []
        for m in matches:
            meta = getattr(m, "metadata", None) or {}
            rows.append(
                {
                    "_id": getattr(m, "id", None),
                    **dict(meta),
                    "_score": getattr(m, "score", None),
                }
            )
        return RowBatch(rows=rows, exhausted=True)

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        _ = filter_ir
        stats = self._sdk().describe_index_stats()
        nss = getattr(stats, "namespaces", None) or {}
        if isinstance(nss, dict) and collection in nss:
            ns = nss[collection]
            return int(getattr(ns, "vector_count", 0) or ns.get("vector_count", 0))
        return int(getattr(stats, "total_vector_count", 0) or 0)

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        _ = collection, n
        return []
