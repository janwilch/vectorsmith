"""Optional rerank hook. Failure keeps vector order."""

from __future__ import annotations

from typing import Any, Protocol


class RerankProvider(Protocol):
    async def rerank(
        self, query: str, rows: list[dict[str, Any]], *, spec: Any
    ) -> list[dict[str, Any]]: ...


class _HTTPRerank:
    async def rerank(
        self, query: str, rows: list[dict[str, Any]], *, spec: Any
    ) -> list[dict[str, Any]]:
        import httpx

        cfg = dict(getattr(spec, "config", {}) or {})
        url = cfg.get("base_url") or cfg.get("url")
        if not url:
            raise RuntimeError("rerank http provider needs config.base_url")
        docs = [_row_text(r) for r in rows]
        headers = dict(cfg.get("headers") or {})
        if cfg.get("api_key"):
            headers.setdefault("Authorization", f"Bearer {cfg['api_key']}")
        async with httpx.AsyncClient(timeout=float(cfg.get("timeout_s") or 30)) as client:
            resp = await client.post(
                str(url),
                json={"query": query, "documents": docs, "model": getattr(spec, "model", "")},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        order = data.get("results") or data.get("indexes") or []
        if not order:
            return rows
        out: list[dict[str, Any]] = []
        for item in order:
            idx = int(item["index"] if isinstance(item, dict) else item)
            if 0 <= idx < len(rows):
                out.append(rows[idx])
        return out or rows


class _CohereRerank:
    async def rerank(
        self, query: str, rows: list[dict[str, Any]], *, spec: Any
    ) -> list[dict[str, Any]]:
        import cohere

        cfg = dict(getattr(spec, "config", {}) or {})
        client = cohere.AsyncClient(api_key=cfg.get("api_key"))
        docs = [_row_text(r) for r in rows]
        resp = await client.rerank(
            model=str(getattr(spec, "model", None) or "rerank-english-v3.0"),
            query=query,
            documents=docs,
        )
        out: list[dict[str, Any]] = []
        for item in resp.results:
            idx = int(item.index)
            if 0 <= idx < len(rows):
                out.append(rows[idx])
        return out or rows


def resolve_rerank_provider(name: str) -> RerankProvider:
    if name == "cohere":
        return _CohereRerank()
    return _HTTPRerank()


def _row_text(row: dict[str, Any]) -> str:
    for key in ("text", "content", "body", "title"):
        val = row.get(key)
        if isinstance(val, str) and val:
            return val
    return " ".join(str(v) for v in row.values() if v is not None and not str(v).startswith("_"))


async def rerank_rows(
    query: str,
    rows: list[dict[str, Any]],
    spec: Any,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    if spec is None or not getattr(spec, "enabled", False) or not rows:
        return rows[:limit], None
    hook = getattr(spec, "_rerank", None)
    try:
        if hook is not None:
            ranked = await hook(query, rows, spec=spec)
        else:
            ranked = await resolve_rerank_provider(getattr(spec, "provider", "http")).rerank(
                query, rows, spec=spec
            )
        return list(ranked)[:limit], None
    except Exception:
        return rows[:limit], "VB4031"
