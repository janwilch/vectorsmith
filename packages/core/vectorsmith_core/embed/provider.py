"""FastEmbed provider (default)."""

from __future__ import annotations

from vectorsmith_core.embed.cache import EmbedCache
from vectorsmith_core.embed.models import resolve_dims
from vectorsmith_core.errors import EmbeddingError
from vectorsmith_core.tds.models import EmbeddingConfig


class FastEmbedProvider:
    """ONNX FastEmbed with a small LRU cache. Requires the ``[embed]`` extra."""

    name = "fastembed"

    def __init__(self) -> None:
        self._cache = EmbedCache()
        self._models: dict[str, object] = {}

    def dims(self, model: str, *, config: EmbeddingConfig | None = None) -> int:
        try:
            return resolve_dims(model, config)
        except EmbeddingError as exc:
            raise EmbeddingError(detail=f"unknown embedding model '{model}'") from exc

    async def health(self) -> bool:
        try:
            import fastembed  # noqa: F401
        except ImportError:
            return False
        return True

    def _model(self, model: str) -> object:
        name = model.split("/", 1)[-1]
        if name.startswith("fastembed/"):
            name = name.split("/", 1)[-1]
        if name not in self._models:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise EmbeddingError(
                    detail="embed extra not installed: pip install 'vectorsmith[qdrant]'"
                ) from exc
            try:
                self._models[name] = TextEmbedding(model_name=name)
            except Exception as exc:
                raise EmbeddingError(detail=str(exc)) from exc
        return self._models[name]

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
        out: list[list[float]] = [None] * len(texts)  # type: ignore[list-item]
        missing: list[tuple[int, str]] = []
        for i, text in enumerate(texts):
            hit = cache.get(self.name, model, text)
            if hit is None:
                missing.append((i, text))
            else:
                out[i] = hit
        if missing:
            try:
                enc = self._model(model)
                vecs = list(enc.embed([t for _i, t in missing]))  # type: ignore[attr-defined]
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError(detail=str(exc)) from exc
            if len(vecs) != len(missing):
                raise EmbeddingError(detail="fastembed response length does not match input")
            for (idx, text), raw in zip(missing, vecs, strict=True):
                row = [float(x) for x in raw]
                cache.put(self.name, model, text, row)
                out[idx] = row
        return out
