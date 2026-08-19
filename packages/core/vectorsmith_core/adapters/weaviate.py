"""Weaviate adapter."""

from __future__ import annotations

from typing import Any, ClassVar

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import WEAVIATE_CAPS
from vectorsmith_core.errors import BackendUnreachable
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or


class WeaviateAdapter(VectorBackendAdapter):
    caps: ClassVar = WEAVIATE_CAPS

    def __init__(self, creds: dict[str, str]) -> None:
        self.url = creds.get("url", "")
        self.api_key = creds.get("api_key")
        self.tenant = creds.get("tenant")
        self._client: Any = None

    def compile_filter(self, node: IRNode | None) -> object:
        if node is None:
            return None
        if isinstance(node, Cond):
            return {"path": [node.path], "operator": node.op, "value": node.value}
        if isinstance(node, And):
            return {"operator": "And", "operands": [self.compile_filter(c) for c in node.children]}
        if isinstance(node, Or):
            return {"operator": "Or", "operands": [self.compile_filter(c) for c in node.children]}
        return None

    def _sdk(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import weaviate  # type: ignore[import-not-found]
            from weaviate.auth import AuthApiKey  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendUnreachable(
                detail="weaviate extra not installed: pip install vectorsmith-core[weaviate]"
            ) from exc
        auth = AuthApiKey(self.api_key) if self.api_key else None
        self._client = weaviate.connect_to_custom(
            http_host=self.url.replace("https://", "").replace("http://", "").split("/")[0],
            http_secure=self.url.startswith("https"),
            auth_credentials=auth,
        )
        return self._client

    async def health(self) -> bool:
        try:
            return bool(self._sdk().is_ready())
        except BackendUnreachable:
            raise
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def list_collections(self) -> list[str]:
        cols = self._sdk().collections.list_all()
        if isinstance(cols, dict):
            return list(cols)
        return [getattr(c, "name", str(c)) for c in cols]

    async def search(self, req: SearchRequest) -> RowBatch:
        coll = self._sdk().collections.get(req.collection)
        if self.tenant:
            coll = coll.with_tenant(self.tenant)
        try:
            if req.vector is None:
                res = coll.query.fetch_objects(limit=req.limit)
            elif req.mode == "hybrid" and req.query_text:
                res = coll.query.hybrid(
                    query=req.query_text,
                    vector=req.vector,
                    limit=req.limit,
                    alpha=req.alpha,
                )
            else:
                res = coll.query.near_vector(near_vector=req.vector, limit=req.limit)
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc
        rows = []
        for obj in getattr(res, "objects", []) or []:
            props = dict(getattr(obj, "properties", None) or {})
            rows.append({"_id": str(getattr(obj, "uuid", "")), **props})
        return RowBatch(rows=rows, exhausted=True)

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        _ = filter_ir
        coll = self._sdk().collections.get(collection)
        if self.tenant:
            coll = coll.with_tenant(self.tenant)
        agg = coll.aggregate.over_all(total_count=True)
        total = getattr(agg, "total_count", 0)
        return int(getattr(total, "real", 0) or total or 0)

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        batch = await self.search(SearchRequest(collection=collection, limit=n))
        return batch.rows

    async def aclose(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close:
                close()
            self._client = None
