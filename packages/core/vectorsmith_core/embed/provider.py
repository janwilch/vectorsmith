"""EmbedProvider implementations."""

from __future__ import annotations

from collections import OrderedDict

from vectorsmith_core.embed.models import DIMS
from vectorsmith_core.errors import EmbeddingError


class FastEmbedProvider:
    """ONNX FastEmbed with a small LRU cache. Requires the ``[embed]`` extra."""

    def __init__(self) -> None:
        self._cache: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
        self._limit = 10_000
        self._models: dict[str, object] = {}

    def dims(self, model: str) -> int:
        key = model.split("/", 1)[-1]
        if key not in DIMS:
            raise EmbeddingError(detail=f"unknown embedding model '{model}'")
        return DIMS[key]

    def _model(self, model: str) -> object:
        name = model.split("/", 1)[-1]
        if name not in self._models:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise EmbeddingError(
                    detail="embed extra not installed: pip install 'vectorsmith-core[embed]'"
                ) from exc
            self._models[name] = TextEmbedding(model_name=name)
        return self._models[name]

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        out: list[list[float]] = []
        missing: list[str] = []
        for t in texts:
            hit = self._cache.get((model, t))
            if hit is None:
                missing.append(t)
            else:
                out.append(hit)
        if missing:
            enc = self._model(model)
            vecs = list(enc.embed(missing))  # type: ignore[attr-defined]
            for t, v in zip(missing, vecs, strict=True):
                row = [float(x) for x in v]
                self._cache[(model, t)] = row
                if len(self._cache) > self._limit:
                    self._cache.popitem(last=False)
                out.append(row)
        return out
