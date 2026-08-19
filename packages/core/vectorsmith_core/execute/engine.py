"""Internal executor used by ``vectorsmith serve`` / ``test`` / ``validate --live``.

Application and agent code must not construct this. Consume tools over MCP.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from vectorsmith_core.errors import InvalidArgumentsError
from vectorsmith_core.execute.single_step import execute_single
from vectorsmith_core.tds.models import ChromaConn, PgvectorConn, QdrantConn

if TYPE_CHECKING:
    from vectorsmith_core.api import (
        CallContext,
        CredentialResolver,
        EmbedProvider,
        HealthStatus,
        Issue,
        Project,
        ToolResult,
    )


class Engine:
    """Internal: execute compiled tools against configured backends.

    Not a public SDK. Agents attach ``vectorsmith serve`` as an MCP client.
    """

    def __init__(
        self,
        project: Project,
        *,
        credential_resolver: CredentialResolver,
        embed_provider: EmbedProvider | None = None,
    ) -> None:
        self.project = project
        self.resolver = credential_resolver
        self.embed = embed_provider
        self._adapters: dict[str, Any] = {}

    async def _adapter(self, connection: str) -> Any:
        if connection in self._adapters:
            return self._adapters[connection]
        spec = self.project.tds.connections[connection]
        creds = await self.resolver.resolve(connection, spec)
        adapter = await _build_adapter(spec, creds.values)
        self._adapters[connection] = adapter
        return adapter

    async def call(
        self,
        tool: str,
        args: dict[str, Any],
        *,
        ctx: CallContext,
        debug: bool = False,
    ) -> ToolResult:
        compiled = self.project.tools.get(tool)
        if compiled is None:
            raise InvalidArgumentsError(
                detail=f"unknown tool '{tool}'; call list_available_tools for the live catalog"
            )
        plan = compiled.plan
        if plan is None:
            raise InvalidArgumentsError(detail=f"tool '{tool}' has no plan")
        if plan.connection is None:
            raise InvalidArgumentsError(detail=f"tool '{tool}' has no connection")
        adapter = await self._adapter(plan.connection)
        started = time.perf_counter()
        if plan.kind == "pipeline":
            from vectorsmith_core.execute.pipeline import execute_pipeline

            result = await execute_pipeline(
                compiled,
                plan,
                args,
                adapter=adapter,
                embed=self.embed,
                ctx=ctx,
                debug=debug,
            )
        else:
            result = await execute_single(
                compiled,
                plan,
                args,
                adapter=adapter,
                embed=self.embed,
                ctx=ctx,
                debug=debug,
            )
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    async def health(self) -> dict[str, HealthStatus]:
        from vectorsmith_core.api import HealthStatus

        out: dict[str, HealthStatus] = {}
        for name in self.project.tds.connections:
            try:
                adapter = await self._adapter(name)
                ok = await adapter.health()
                out[name] = HealthStatus(ok=ok, detail="ok" if ok else "unhealthy")
            except Exception as exc:  # noqa: BLE001 — mapped at boundary
                out[name] = HealthStatus(ok=False, detail=str(exc))
        return out

    async def introspect(
        self,
        connection: str,
        collections: list[str] | None = None,
        sample_n: int = 200,
        redact_examples: bool = False,
    ) -> dict[str, Any]:
        from vectorsmith_core.introspect.sampling import infer_fields
        from vectorsmith_core.introspect.schema_export import to_schema_json

        adapter = await self._adapter(connection)
        names = collections or await adapter.list_collections()
        cols = []
        for c in names:
            native = await adapter.introspect_native(c)
            sample = await adapter.sample(c, sample_n)
            fields = infer_fields(sample, redact_examples=redact_examples)
            cols.append(
                {
                    "name": c,
                    "native": native,
                    "sampled_n": len(sample),
                    "fields": fields,
                    "vector": {"sparse": bool((native or {}).get("sparse"))},
                }
            )
        report = {
            "connection": connection,
            "backend": self.project.tds.connections[connection].backend,
            "collections": cols,
            "redacted": redact_examples,
        }
        return to_schema_json(report)

    async def validate_live(self) -> list[Issue]:
        from vectorsmith_core.api import Issue
        from vectorsmith_core.compilepkg.validator import validate

        sparse: dict[str, bool] = {}
        extra: list[Issue] = []
        for name in self.project.tds.connections:
            try:
                adapter = await self._adapter(name)
                ok = await adapter.health()
                if not ok:
                    extra.append(
                        Issue(
                            severity="error",
                            code="VB4003",
                            message=f"connection '{name}' is unhealthy",
                            path=name,
                        )
                    )
                collections = await adapter.list_collections()
                for coll in collections:
                    native = await adapter.introspect_native(coll)
                    sparse[f"{name}:{coll}"] = bool(native and native.get("sparse"))
            except Exception as exc:  # noqa: BLE001
                extra.append(
                    Issue(
                        severity="error",
                        code="backend_unreachable",
                        message=str(exc),
                        path=name,
                    )
                )
        extra.extend(validate(self.project.tds, live_sparse=sparse))
        seen = {(i.code, i.tool, i.path, i.message) for i in self.project.issues}
        out = list(self.project.issues)
        for issue in extra:
            key = (issue.code, issue.tool, issue.path, issue.message)
            if key not in seen:
                out.append(issue)
        return out

    async def aclose(self) -> None:
        for a in self._adapters.values():
            close = getattr(a, "aclose", None)
            if close:
                await close()
        self._adapters.clear()

    async def __aenter__(self) -> Engine:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


async def _build_adapter(spec: object, creds: dict[str, str]) -> Any:
    backend = spec.backend
    if backend == "qdrant":
        from vectorsmith_core.adapters.qdrant import QdrantAdapter

        if not isinstance(spec, QdrantConn):
            raise InvalidArgumentsError(detail="qdrant connection mismatch")
        return QdrantAdapter(url=creds.get("url") or spec.url, api_key=creds.get("api_key"))
    if backend == "pgvector":
        from vectorsmith_core.adapters.pgvector import PgvectorAdapter

        if not isinstance(spec, PgvectorConn):
            raise InvalidArgumentsError(detail="pgvector connection mismatch")
        return PgvectorAdapter(spec, creds)
    if backend == "chroma":
        from vectorsmith_core.adapters.chroma import ChromaAdapter

        if not isinstance(spec, ChromaConn):
            raise InvalidArgumentsError(detail="chroma connection mismatch")
        return ChromaAdapter(url=creds.get("url") or spec.url, auth_token=creds.get("auth_token"))
    if backend == "pinecone":
        from vectorsmith_core.adapters.pinecone import PineconeAdapter

        return PineconeAdapter(creds)
    if backend == "weaviate":
        from vectorsmith_core.adapters.weaviate import WeaviateAdapter

        return WeaviateAdapter(creds)
    if backend == "milvus":
        from vectorsmith_core.adapters.milvus import MilvusAdapter

        return MilvusAdapter(creds)
    raise InvalidArgumentsError(detail=f"unknown backend {backend}")

