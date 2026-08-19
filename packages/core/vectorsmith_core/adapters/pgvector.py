"""pgvector adapter (vector + table mode). SQL via psycopg.sql only."""

from __future__ import annotations

from typing import Any, ClassVar

from vectorsmith_core.adapters.base import RowBatch, SearchRequest, VectorBackendAdapter
from vectorsmith_core.adapters.capabilities import PGVECTOR_CAPS
from vectorsmith_core.errors import BackendUnreachable, InvalidArgumentsError
from vectorsmith_core.ir.filter import And, Cond, IRNode, Or
from vectorsmith_core.tds.models import PgvectorConn, is_table_mode


class PgvectorAdapter(VectorBackendAdapter):
    caps: ClassVar = PGVECTOR_CAPS

    def __init__(self, spec: PgvectorConn, creds: dict[str, str]) -> None:
        self.spec = spec
        self.dsn = creds.get("dsn") or spec.dsn
        self.vector_capable = not is_table_mode(spec)
        self._pool: Any = None

    def _ident(self) -> Any:
        from psycopg import sql  # type: ignore[import-not-found]

        table = self.spec.table or "invoices"
        return sql.Identifier(*table.split(".")) if "." in table else sql.Identifier(table)

    def compile_filter(self, node: IRNode | None) -> object:
        from psycopg import sql  # type: ignore[import-not-found]

        params: list[Any] = []
        clause = _sql_clause(node, params)
        return {"sql": clause, "params": params, "composed": sql.SQL("{}").format(clause)}

    async def _conn(self) -> Any:
        try:
            from psycopg_pool import AsyncConnectionPool  # type: ignore[import-not-found]
        except ImportError as exc:
            raise BackendUnreachable(
                detail="pgvector extra not installed: pip install vectorsmith-core[pgvector]"
            ) from exc
        if self._pool is None:
            self._pool = AsyncConnectionPool(conninfo=self.dsn, min_size=1, max_size=8, open=False)
            await self._pool.open()
        return self._pool

    async def health(self) -> bool:
        try:
            pool = await self._conn()
            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except BackendUnreachable:
            raise
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def list_collections(self) -> list[str]:
        return [self.spec.table] if self.spec.table else []

    async def search(self, req: SearchRequest) -> RowBatch:
        if not self.vector_capable:
            raise InvalidArgumentsError(
                detail="table mode does not support search — use lookup/count/scroll/pipeline"
            )
        if req.vector is None:
            return await self._scroll(req)
        from psycopg import sql  # type: ignore[import-not-found]

        compiled = self.compile_filter(
            req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else None
        )
        params = list(compiled["params"]) if isinstance(compiled, dict) else []
        vec_col = sql.Identifier(self.spec.vector_column or "embedding")
        id_col = sql.Identifier(self.spec.id_column)
        where = compiled["sql"] if isinstance(compiled, dict) else sql.SQL("TRUE")
        params.append(req.vector)
        params.append(req.limit)
        query = sql.SQL(
            "SELECT {id} AS _id, * , ({vec} <=> %s::vector) AS _score "
            "FROM {table} WHERE {where} ORDER BY {vec} <=> %s::vector LIMIT %s"
        ).format(id=id_col, vec=vec_col, table=self._ident(), where=where)
        # second vec compare uses same vector — pass twice
        params.insert(-1, req.vector)
        try:
            pool = await self._conn()
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(query, params)
                cols = [d.name for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, row, strict=False)) for row in await cur.fetchall()]
            return RowBatch(rows=rows, exhausted=len(rows) < req.limit)
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def _scroll(self, req: SearchRequest) -> RowBatch:
        from psycopg import sql  # type: ignore[import-not-found]

        compiled = self.compile_filter(
            req.filter_ir if isinstance(req.filter_ir, (And, Or, Cond)) else None
        )
        params = list(compiled["params"]) if isinstance(compiled, dict) else []
        where = compiled["sql"] if isinstance(compiled, dict) else sql.SQL("TRUE")
        id_col = sql.Identifier(self.spec.id_column)
        params.append(req.limit)
        query = sql.SQL("SELECT {id} AS _id, * FROM {table} WHERE {where} LIMIT %s").format(
            id=id_col, table=self._ident(), where=where
        )
        try:
            pool = await self._conn()
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(query, params)
                cols = [d.name for d in cur.description] if cur.description else []
                rows = [dict(zip(cols, row, strict=False)) for row in await cur.fetchall()]
            return RowBatch(rows=rows, exhausted=len(rows) < req.limit)
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def count(self, collection: str, filter_ir: IRNode | None) -> int:
        from psycopg import sql  # type: ignore[import-not-found]

        _ = collection
        compiled = self.compile_filter(filter_ir)
        params = list(compiled["params"]) if isinstance(compiled, dict) else []
        where = compiled["sql"] if isinstance(compiled, dict) else sql.SQL("TRUE")
        query = sql.SQL("SELECT count(*) FROM {table} WHERE {where}").format(
            table=self._ident(), where=where
        )
        try:
            pool = await self._conn()
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
            return int(row[0]) if row else 0
        except Exception as exc:
            raise BackendUnreachable(detail=str(exc)) from exc

    async def sample(self, collection: str, n: int) -> list[dict[str, Any]]:
        batch = await self._scroll(
            SearchRequest(collection=collection or (self.spec.table or ""), limit=n)
        )
        return batch.rows

    async def aclose(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def _sql_clause(node: IRNode | None, params: list[Any]) -> Any:
    from psycopg import sql  # type: ignore[import-not-found]

    if node is None:
        return sql.SQL("TRUE")
    if isinstance(node, And):
        parts = [_sql_clause(c, params) for c in node.children]
        return sql.SQL(" AND ").join(sql.SQL("(") + p + sql.SQL(")") for p in parts)
    if isinstance(node, Or):
        parts = [_sql_clause(c, params) for c in node.children]
        return sql.SQL(" OR ").join(sql.SQL("(") + p + sql.SQL(")") for p in parts)
    assert isinstance(node, Cond)
    col = sql.SQL("payload->>{}").format(sql.Literal(node.path))
    if node.op == "eq":
        params.append(node.value)
        return col + sql.SQL(" = %s")
    if node.op == "ne":
        params.append(node.value)
        return col + sql.SQL(" <> %s")
    if node.op in {"gt", "gte", "lt", "lte"}:
        ops = {
            "gt": sql.SQL(" > %s"),
            "gte": sql.SQL(" >= %s"),
            "lt": sql.SQL(" < %s"),
            "lte": sql.SQL(" <= %s"),
        }
        params.append(node.value)
        return col + ops[node.op]
    if node.op == "in":
        params.append(list(node.value) if not isinstance(node.value, list) else node.value)
        return col + sql.SQL(" = ANY(%s)")
    if node.op == "nin":
        params.append(list(node.value) if not isinstance(node.value, list) else node.value)
        return col + sql.SQL(" <> ALL(%s)")
    return sql.SQL("TRUE")
