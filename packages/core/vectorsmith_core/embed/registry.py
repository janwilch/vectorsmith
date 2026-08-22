"""Resolve named embedding providers."""

from __future__ import annotations

from typing import Any

from vectorsmith_core.errors import EmbeddingError

_PROVIDERS: dict[str, Any] = {}


def _missing(extra: str, pip: str) -> EmbeddingError:
    return EmbeddingError(detail=f"{extra} extra not installed: pip install '{pip}'")


def provider_available(name: str) -> bool:
    if name in {"fastembed", "http"}:
        return True
    if name in {"openai", "azure_openai"}:
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True
    if name == "cohere":
        try:
            import cohere  # noqa: F401
        except ImportError:
            return False
        return True
    return False


def resolve_provider(name: str) -> Any:
    if name in _PROVIDERS:
        return _PROVIDERS[name]
    inst: Any
    if name == "fastembed":
        from vectorsmith_core.embed.provider import FastEmbedProvider

        inst = FastEmbedProvider()
    elif name == "openai":
        from vectorsmith_core.embed.openai import OpenAIEmbedProvider

        inst = OpenAIEmbedProvider()
    elif name == "azure_openai":
        from vectorsmith_core.embed.openai import AzureOpenAIEmbedProvider

        inst = AzureOpenAIEmbedProvider()
    elif name == "http":
        from vectorsmith_core.embed.http import HttpEmbedProvider

        inst = HttpEmbedProvider()
    elif name == "cohere":
        from vectorsmith_core.embed.cohere import CohereEmbedProvider

        inst = CohereEmbedProvider()
    else:
        raise EmbeddingError(detail=f"unknown embedding provider '{name}'")
    _PROVIDERS[name] = inst
    return inst


def reset_providers() -> None:
    _PROVIDERS.clear()
