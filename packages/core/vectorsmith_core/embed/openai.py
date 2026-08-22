"""OpenAI and Azure OpenAI embedding providers."""

from __future__ import annotations

from typing import Any

from vectorsmith_core.embed.cache import EmbedCache
from vectorsmith_core.embed.models import resolve_dims
from vectorsmith_core.errors import EmbeddingError
from vectorsmith_core.tds.models import EmbeddingConfig


def _import_openai() -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise EmbeddingError(
            detail="embed-openai extra not installed: pip install 'vectorsmith[embed-openai]'"
        ) from exc
    return AsyncOpenAI


class OpenAIEmbedProvider:
    name = "openai"

    def __init__(self) -> None:
        self._cache = EmbedCache()

    def dims(self, model: str, *, config: EmbeddingConfig | None = None) -> int:
        return resolve_dims(model, config)

    async def health(self) -> bool:
        try:
            _import_openai()
        except EmbeddingError:
            return False
        return True

    def _client(self, cfg: dict[str, Any]) -> Any:
        AsyncOpenAI = _import_openai()
        kwargs: dict[str, Any] = {}
        if cfg.get("api_key"):
            kwargs["api_key"] = cfg["api_key"]
        if cfg.get("base_url"):
            kwargs["base_url"] = cfg["base_url"]
        if cfg.get("timeout_s"):
            kwargs["timeout"] = float(cfg["timeout_s"])
        return AsyncOpenAI(**kwargs)

    async def embed(
        self,
        texts: list[str],
        model: str,
        *,
        config: EmbeddingConfig | None = None,
    ) -> list[list[float]]:
        return await _embed_openai(
            self, texts, model, config=config, azure=False
        )


class AzureOpenAIEmbedProvider:
    name = "azure_openai"

    def __init__(self) -> None:
        self._cache = EmbedCache()

    def dims(self, model: str, *, config: EmbeddingConfig | None = None) -> int:
        return resolve_dims(model, config)

    async def health(self) -> bool:
        try:
            from openai import AsyncAzureOpenAI  # noqa: F401
        except ImportError:
            return False
        return True

    def _client(self, cfg: dict[str, Any]) -> Any:
        try:
            from openai import AsyncAzureOpenAI
        except ImportError as exc:
            raise EmbeddingError(
                detail="embed-openai extra not installed: pip install 'vectorsmith[embed-openai]'"
            ) from exc
        kwargs: dict[str, Any] = {
            "azure_endpoint": cfg.get("endpoint") or cfg.get("base_url") or "",
            "api_version": cfg.get("api_version") or "2024-02-01",
        }
        if cfg.get("api_key"):
            kwargs["api_key"] = cfg["api_key"]
        if cfg.get("timeout_s"):
            kwargs["timeout"] = float(cfg["timeout_s"])
        return AsyncAzureOpenAI(**kwargs)

    async def embed(
        self,
        texts: list[str],
        model: str,
        *,
        config: EmbeddingConfig | None = None,
    ) -> list[list[float]]:
        return await _embed_openai(self, texts, model, config=config, azure=True)


async def _embed_openai(
    provider: OpenAIEmbedProvider | AzureOpenAIEmbedProvider,
    texts: list[str],
    model: str,
    *,
    config: EmbeddingConfig | None,
    azure: bool,
) -> list[list[float]]:
    cfg = dict(config.config) if config is not None else {}
    ttl = cfg.get("cache_ttl_s")
    cache = EmbedCache(ttl_s=float(ttl)) if ttl is not None else provider._cache
    out: list[list[float] | None] = [None] * len(texts)
    missing: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        hit = cache.get(provider.name, model, text)
        if hit is None:
            missing.append((i, text))
        else:
            out[i] = hit
    if not missing:
        return [v for v in out if v is not None]
    batch_size = int(cfg.get("batch_size") or 32)
    retries = int(cfg.get("max_retries") or 6)
    backoff = float(cfg.get("retry_backoff_s") or 1.0)
    use_model = str(cfg.get("deployment") or model) if azure else model
    client = provider._client(cfg)
    try:
        import asyncio

        for start in range(0, len(missing), batch_size):
            chunk = missing[start : start + batch_size]
            last_exc: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    resp = await client.embeddings.create(
                        model=use_model, input=[t for _i, t in chunk]
                    )
                    rows = list(getattr(resp, "data", None) or [])
                    if len(rows) != len(chunk):
                        raise EmbeddingError(
                            detail="openai embed response length does not match input"
                        )
                    for (idx, text), row in zip(chunk, rows, strict=True):
                        vec = [float(x) for x in row.embedding]
                        cache.put(provider.name, model, text, vec)
                        out[idx] = vec
                    last_exc = None
                    break
                except EmbeddingError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    if attempt >= retries:
                        break
                    await asyncio.sleep(backoff * (attempt + 1))
            if last_exc is not None:
                raise EmbeddingError(detail=str(last_exc)) from last_exc
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(detail=str(exc)) from exc
    return [v if v is not None else [] for v in out]
