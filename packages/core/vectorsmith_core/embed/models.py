"""Embedding model name → dimension registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vectorsmith_core.errors import EmbeddingError

if TYPE_CHECKING:
    from vectorsmith_core.tds.models import EmbeddingConfig

BUILTIN_DIMS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
    "bge-small-en-v1.5": 384,
    "fastembed/BAAI/bge-small-en-v1.5": 384,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "embed-english-v3.0": 1024,
    "embed-multilingual-v3.0": 1024,
}

DIMS = BUILTIN_DIMS


def resolve_dims(model: str, config: EmbeddingConfig | None = None) -> int:
    """Return vector size. ``config.dims`` wins; else the built-in registry."""
    if config is not None and config.dims is not None:
        return int(config.dims)
    if model in BUILTIN_DIMS:
        return BUILTIN_DIMS[model]
    short = model.split("/", 1)[-1]
    if short in BUILTIN_DIMS:
        return BUILTIN_DIMS[short]
    raise EmbeddingError(
        detail=f"unknown model dims for '{model}'; set dims explicitly"
    )
