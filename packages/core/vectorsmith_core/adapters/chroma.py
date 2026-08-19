"""Chroma adapter — where-dicts, single-condition unwrap."""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import CHROMA_CAPS
from vectorsmith_core.errors import BackendUnreachable
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or

_OP = {
    "eq": "$eq",
    "ne": "$ne",
    "gt": "$gt",
    "gte": "$gte",
    "lt": "$lt",
    "lte": "$lte",
    "in": "$in",
    "nin": "$nin",
}


class ChromaAdapter(VectorBackendAdapter):
    caps: ClassVar = CHROMA_CAPS

    def __init__(self, url: str, auth_token: str | None = None) -> None:
        self.url = url
        self.auth_token = auth_token
        self._client: Any = None

    def compile_filter(self, node: IRNode | None) -> object:
        if node is None:
            return None
        if isinstance(node, Cond):
            return {node.path: {_OP.get(node.op, "$eq"): node.value}}
        if isinstance(node, And):
            kids = [self.compile_filter(c) for c in node.children]
            return kids[0] if len(kids) == 1 else {"$and": kids}
        if isinstance(node, Or):
            kids = [self.compile_filter(c) for c in node.children]
            return kids[0] if len(kids) == 1 else {"$or": kids}
        return None

    async def _sdk(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import chromadb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendUnreachable(
                detail="chroma extra not installed: pip install vectorsmith-core[chroma]"
            ) from exc
        parsed = urlparse(self.url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000
        try:
            self._client = await chromadb.AsyncHttpClient(host=host, port=port)
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc
        return self._client

    async def health(self) -> bool:
        client = await self._sdk()
        await client.heartbeat()
        return True

    async def list_collections(self) -> list[str]:
        client = await self._sdk()
        cols = await client.list_collections()
        return [getattr(c, "name", str(c)) for c in cols]

    async def search(self, req: SearchRequest) -> RowBatch:
        client = await self._sdk()
        coll = await client.get_collection(req.collection)
        where = self.compile_filter(
            req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else None
        )
        try:
            if req.vector is None:
                res = await coll.get(where=where, limit=req.limit, include=["metadatas"])
            else:
                res = await coll.query(
                    query_embeddings=[req.vector],
                    n_results=req.limit,
                    where=where,
                    include=["metadatas", "distances"],
                )
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc
        rows = _chroma_rows(res)
        return RowBatch(rows=rows, exhausted=len(rows) < req.limit)

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        client = await self._sdk()
        coll = await client.get_collection(collection)
        where = self.compile_filter(filter_ir)
        try:
            if where is None:
                return int(await coll.count())
            got = await coll.get(where=where)
            return len(got.get("ids") or [])
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        batch = await self.search(SearchRequest(collection=collection, limit=n))
        return batch.rows


def _chroma_rows(res: Any) -> list[dict[str, Any]]:
    if isinstance(res, dict):
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        dists = res.get("distances")
        if ids and isinstance(ids[0], list):
            ids, metas = ids[0], (metas[0] if metas else [])
            dists = dists[0] if dists else None
        rows = []
        for i, pid in enumerate(ids):
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            row = {"_id": pid, **meta}
            if dists is not None and i < len(dists):
                row["_score"] = dists[i]
            rows.append(row)
        return rows
    return []
