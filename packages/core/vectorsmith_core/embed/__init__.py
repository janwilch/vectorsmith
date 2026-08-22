"""Embedding providers."""

from vectorsmith_core.embed.models import BUILTIN_DIMS, DIMS, resolve_dims
from vectorsmith_core.embed.provider import FastEmbedProvider
from vectorsmith_core.embed.registry import resolve_provider

__all__ = [
    "BUILTIN_DIMS",
    "DIMS",
    "FastEmbedProvider",
    "resolve_dims",
    "resolve_provider",
]
