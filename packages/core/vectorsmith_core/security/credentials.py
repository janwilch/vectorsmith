"""Pluggable credential backends. Default remains env."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from vectorsmith_core.api import EnvCredentialResolver, ResolvedCredentials
from vectorsmith_core.errors import MissingEnvError
from vectorsmith_core.tds.models import ConnectionCredentials, VaultCredSpec

VaultFetch = Callable[[VaultCredSpec], Awaitable[Mapping[str, str]]]


class VaultCredentialResolver:
    def __init__(
        self,
        *,
        fetch: VaultFetch | None = None,
        ttl_s: int = 300,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._env = EnvCredentialResolver(env)
        self._fetch = fetch
        self._ttl = ttl_s
        self._cache: dict[tuple[str, str], tuple[float, dict[str, str]]] = {}

    async def resolve(self, name: str, spec: object) -> ResolvedCredentials:
        creds = getattr(spec, "credentials", None)
        provider = getattr(creds, "provider", "env") if creds is not None else "env"
        if provider != "vault":
            return await self._env.resolve(name, spec)
        vault = creds.vault if isinstance(creds, ConnectionCredentials) else None
        path = getattr(vault, "path", None) or f"secret/data/{name}"
        key = (name, path)
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return ResolvedCredentials(values=dict(hit[1]))
        if self._fetch is None:
            raise MissingEnvError(
                [path],
                detail=f"vault fetch not configured for '{name}' path '{path}'",
            )
        try:
            data = dict(await self._fetch(vault or VaultCredSpec(path=path)))
        except MissingEnvError:
            raise
        except Exception as exc:
            raise MissingEnvError([path], detail=f"vault secret missing at '{path}'") from exc
        if not data:
            raise MissingEnvError([path], detail=f"vault secret missing at '{path}'")
        self._cache[key] = (now + self._ttl, data)
        return ResolvedCredentials(values=data)


def build_credential_resolver(
    env: Mapping[str, str] | None = None,
    *,
    vault_fetch: VaultFetch | None = None,
) -> Any:
    if vault_fetch is None:
        return EnvCredentialResolver(env)
    return VaultCredentialResolver(fetch=vault_fetch, env=env)
