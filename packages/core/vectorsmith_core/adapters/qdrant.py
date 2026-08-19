"""Qdrant adapter — dense (+ hybrid when sparse is configured)."""

from __future__ import annotations

from typing import Any, ClassVar

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import QDRANT_CAPS
from vectorsmith_core.errors import BackendUnreachable
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or


def _match(cond: Cond) -> dict[str, Any]:
    path, op, value = cond.path, cond.op, cond.value
    if op in {"eq"}:
        return {"key": path, "match": {"value": value}}
    if op == "ne":
        return {"must_not": [{"key": path, "match": {"value": value}}]}
    if op == "in":
        return {"key": path, "match": {"any": value}}
    if op == "nin":
        return {"key": path, "match": {"except": value}}
    if op in {"gt", "gte", "lt", "lte"}:
        rng: dict[str, Any] = {}
        if op == "gt":
            rng["gt"] = value
        elif op == "gte":
            rng["gte"] = value
        elif op == "lt":
            rng["lt"] = value
        else:
            rng["lte"] = value
        return {"key": path, "range": rng}
    if op == "exists":
        return (
            {"is_empty": {"key": path}} if not value else {"key": path, "match": {"value": value}}
        )
    if op == "is_null":
        return {"is_null": {"key": path}}
    raise BackendUnreachable(detail=f"unsupported op {op}")  # should be VB2004 earlier


class QdrantAdapter(VectorBackendAdapter):
    caps: ClassVar = QDRANT_CAPS

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self._client: Any = None

    def _sdk(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import AsyncQdrantClient
        except ImportError as exc:
            raise BackendUnreachable(
                detail="qdrant extra not installed: pip install vectorsmith-core[qdrant]"
            ) from exc
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        if parsed.port is not None:
            port = parsed.port
        elif parsed.scheme == "https":
            port = 443
        else:
            port = 6333
        key = self.api_key or None
        self._client = AsyncQdrantClient(
            url=self.url,
            api_key=key,
            port=port,
            prefer_grpc=False,
            timeout=60,
            check_compatibility=False,
        )
        return self._client

    def compile_filter(self, node: IRNode | None) -> object:
        if node is None:
            return None
        if isinstance(node, Cond):
            piece = _match(node)
            if "must_not" in piece:
                return {"must_not": piece["must_not"]}
            return {"must": [piece]}
        if isinstance(node, And):
            must: list[Any] = []
            must_not: list[Any] = []
            for child in node.children:
                compiled = self.compile_filter(child)
                if not isinstance(compiled, dict):
                    continue
                must.extend(compiled.get("must") or [])
                must_not.extend(compiled.get("must_not") or [])
                if "should" in compiled:
                    must.append({"should": compiled["should"]})
            out: dict[str, Any] = {}
            if must:
                out["must"] = must
            if must_not:
                out["must_not"] = must_not
            return out or None
        if isinstance(node, Or):
            return {"should": [self.compile_filter(c) for c in node.children]}
        return None

    async def health(self) -> bool:
        try:
            await self._sdk().get_collections()
            return True
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def list_collections(self) -> list[str]:
        res = await self._sdk().get_collections()
        return [c.name for c in res.collections]

    async def search(self, req: SearchRequest) -> RowBatch:
        client = self._sdk()
        qfilter = self.compile_filter(
            req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else req.filter_ir
        )  # type: ignore[arg-type]
        from qdrant_client.http import models as qm

        native = None
        if isinstance(qfilter, dict):
            native = qm.Filter(**qfilter)
        point_id = _lookup_id(req.filter_ir)
        if req.vector is None and point_id is not None:
            points = await client.retrieve(
                collection_name=req.collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
            return RowBatch(rows=[_row(p, None) for p in points], exhausted=True)
        if req.mode == "hybrid":
            native_info = await self.introspect_native(req.collection)
            if not native_info or not native_info.get("sparse"):
                raise BackendUnreachable(
                    detail="VB2013 hybrid requires collection sparse vector config"
                )
            return await self._hybrid_search(client, req, native)
        if req.vector is None:
            points, _ = await client.scroll(
                collection_name=req.collection,
                scroll_filter=native,
                limit=req.limit,
                with_payload=True,
                with_vectors=False,
            )
            rows = [_row(p, None) for p in points]
            return RowBatch(rows=rows, exhausted=len(points) < req.limit)
        if hasattr(client, "query_points"):
            res = await client.query_points(
                collection_name=req.collection,
                query=req.vector,
                query_filter=native,
                limit=req.limit,
                with_payload=True,
            )
            hits = getattr(res, "points", res)
        else:
            hits = await client.search(
                collection_name=req.collection,
                query_vector=req.vector,
                query_filter=native,
                limit=req.limit,
                with_payload=True,
            )
        rows = [_row(h, getattr(h, "score", None)) for h in hits]
        return RowBatch(rows=rows, exhausted=True)

    async def _hybrid_search(self, client: Any, req: SearchRequest, native: object) -> RowBatch:
        from qdrant_client.http import models as qm

        prefetch = []
        if req.vector is not None:
            prefetch.append(qm.Prefetch(query=req.vector, limit=max(req.limit * 2, 20)))
        if req.query_text:
            try:
                prefetch.append(
                    qm.Prefetch(
                        query=qm.Document(text=req.query_text, model="qdrant/bm25"),
                        limit=max(req.limit * 2, 20),
                    )
                )
            except Exception:
                prefetch.append(qm.Prefetch(query=req.vector, limit=max(req.limit * 2, 20)))
        query: object
        if hasattr(qm, "FusionQuery"):
            query = qm.FusionQuery(fusion=qm.Fusion.RRF)
        else:
            query = req.vector
        res = await client.query_points(
            collection_name=req.collection,
            prefetch=prefetch or None,
            query=query,
            query_filter=native,
            limit=req.limit,
            with_payload=True,
        )
        hits = getattr(res, "points", res)
        rows = [_row(h, getattr(h, "score", None)) for h in hits]
        return RowBatch(rows=rows, exhausted=True)

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        qfilter = self.compile_filter(filter_ir)
        from qdrant_client.http import models as qm

        native = qm.Filter(**qfilter) if isinstance(qfilter, dict) else None
        res = await self._sdk().count(collection_name=collection, count_filter=native)
        return int(res.count)

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        points, _ = await self._sdk().scroll(collection_name=collection, limit=n, with_payload=True)
        return [_row(p, None) for p in points]

    async def introspect_native(self, collection: str | None = None) -> dict[str, Any] | None:
        if collection is None:
            return None
        info = await self._sdk().get_collection(collection)
        sparse = False
        params = getattr(info, "config", None)
        # sparse vectors appear on collection params when configured
        if params is not None:
            sparse_cfg = getattr(getattr(params, "params", params), "sparse_vectors", None)
            sparse = bool(sparse_cfg)
        return {"sparse": sparse, "indexed": True}

    async def aclose(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close:
                await close()
            self._client = None


def _lookup_id(node: object) -> int | str | None:
    """Builtin get_by_id filters on path ``id`` — that is the Qdrant point id."""
    if isinstance(node, And):
        found: int | str | None = None
        for child in node.children:
            hit = _lookup_id(child)
            if hit is not None:
                found = hit
        return found
    if not isinstance(node, Cond) or node.path != "id" or node.op != "eq":
        return None
    value = node.value
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, str) and value:
        return value
    return None


def _row(point: Any, score: float | None) -> dict[str, Any]:
    payload = dict(getattr(point, "payload", None) or {})
    pid = getattr(point, "id", None)
    row: dict[str, Any] = {"_id": pid, **payload}
    if score is not None:
        row["_score"] = score
    return row
