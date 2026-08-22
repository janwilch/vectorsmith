"""Cohere embedding provider."""

from __future__ import annotations

from typing import Any

from vectorsmith_core.embed.cache import EmbedCache
from vectorsmith_core.embed.models import resolve_dims
from vectorsmith_core.errors import EmbeddingError
from vectorsmith_core.tds.models import EmbeddingConfig


class CohereEmbedProvider:
    name = "cohere"

    def __init__(self) -> None:
        self._cache = EmbedCache()

    def dims(self, model: str, *, config: EmbeddingConfig | None = None) -> int:
        return resolve_dims(model, config)

    async def health(self) -> bool:
        try:
            import cohere  # noqa: F401
        except ImportError:
            return False
        return True

    def _client(self, cfg: dict[str, Any]) -> Any:
        try:
            import cohere
        except ImportError as exc:
            raise EmbeddingError(
                detail="embed-cohere extra not installed: pip install 'vectorsmith[embed-cohere]'"
            ) from exc
        kwargs: dict[str, Any] = {}
        if cfg.get("api_key"):
            kwargs["api_key"] = cfg["api_key"]
        client = getattr(cohere, "AsyncClientV2", None) or getattr(cohere, "AsyncClient", None)
        if client is None:
            raise EmbeddingError(detail="cohere SDK has no async client")
        return client(**kwargs)

    async def embed(
        self,
        texts: list[str],
        model: str,
        *,
        config: EmbeddingConfig | None = None,
    ) -> list[list[float]]:
        cfg = dict(config.config) if config is not None else {}
        ttl = cfg.get("cache_ttl_s")
        cache = EmbedCache(ttl_s=float(ttl)) if ttl is not None else self._cache
        out: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str]] = []
        for i, text in enumerate(texts):
            hit = cache.get(self.name, model, text)
            if hit is None:
                missing.append((i, text))
            else:
                out[i] = hit
        if not missing:
            return [v for v in out if v is not None]
        batch_size = int(cfg.get("batch_size") or 32)
        use_model = str(cfg.get("model") or model)
        client = self._client(cfg)
        try:
            for start in range(0, len(missing), batch_size):
                chunk = missing[start : start + batch_size]
                resp = await client.embed(
                    texts=[t for _i, t in chunk],
                    model=use_model,
                    input_type=cfg.get("input_type") or "search_query",
                )
                rows = getattr(resp, "embeddings", None)
                if rows is None and isinstance(resp, dict):
                    rows = resp.get("embeddings")
                float_rows = getattr(rows, "float", rows)
                if float_rows is None:
                    raise EmbeddingError(detail="cohere embed response missing embeddings")
                vecs = list(float_rows)
                if len(vecs) != len(chunk):
                    raise EmbeddingError(
                        detail="cohere embed response length does not match input"
                    )
                for (idx, text), vec in zip(chunk, vecs, strict=True):
                    row = [float(x) for x in vec]
                    cache.put(self.name, model, text, row)
                    out[idx] = row
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(detail=str(exc)) from exc
        return [v if v is not None else [] for v in out]
