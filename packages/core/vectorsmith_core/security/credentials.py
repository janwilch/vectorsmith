"""Pluggable credential backends. Default remains env."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from vectorsmith_core.api import EnvCredentialResolver, ResolvedCredentials
from vectorsmith_core.errors import MissingEnvError
from vectorsmith_core.tds.models import (
    AwsSmSpec,
    ConnectionCredentials,
    K8sSpec,
    VaultCredSpec,
)

VaultFetch = Callable[[VaultCredSpec], Awaitable[Mapping[str, str]]]
AwsFetch = Callable[[AwsSmSpec], Awaitable[Mapping[str, str]]]
K8sFetch = Callable[[K8sSpec], Awaitable[Mapping[str, str]]]


def _as_str_map(data: Mapping[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in data.items() if v is not None}


async def default_vault_fetch(spec: VaultCredSpec) -> Mapping[str, str]:
    import httpx

    addr = spec.addr or os.environ.get("VAULT_ADDR")
    token = os.environ.get("VAULT_TOKEN")
    path = spec.path or ""
    if not addr or not token or not path:
        raise MissingEnvError(
            [p for p in ("VAULT_ADDR", "VAULT_TOKEN", path or "vault.path") if p],
            detail="vault requires VAULT_ADDR, VAULT_TOKEN, and credentials.vault.path",
        )
    url = f"{addr.rstrip('/')}/v1/{path.lstrip('/')}"
    headers = {"X-Vault-Token": token}
    if spec.role:
        headers["X-Vault-Role"] = spec.role
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        body = resp.json()
    wrapped = body.get("data")
    if isinstance(wrapped, dict) and isinstance(wrapped.get("data"), dict):
        wrapped = wrapped["data"]
    if not isinstance(wrapped, dict):
        return {}
    return _as_str_map(wrapped)


async def default_aws_sm_fetch(spec: AwsSmSpec) -> Mapping[str, str]:
    if not spec.secret_id:
        raise MissingEnvError(
            ["aws_sm.secret_id"],
            detail="aws_sm requires credentials.aws_sm.secret_id",
        )
    try:
        import boto3
    except ImportError as exc:
        raise MissingEnvError(
            [spec.secret_id],
            detail="aws_sm extra not installed: pip install 'vectorsmith[creds-aws]'",
        ) from exc
    region = spec.region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    client = boto3.client("secretsmanager", region_name=region)
    resp = await asyncio.to_thread(client.get_secret_value, SecretId=spec.secret_id)
    raw = resp.get("SecretString") or ""
    if not raw:
        binary = resp.get("SecretBinary")
        if binary:
            raw = bytes(binary).decode()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"value": raw}
    if isinstance(parsed, dict):
        return _as_str_map(parsed)
    return {"value": str(parsed)}


def _incluster_sa(namespace: str | None) -> tuple[str, str, str | bool, str]:
    sa_dir = "/var/run/secrets/kubernetes.io/serviceaccount"
    token_file = f"{sa_dir}/token"
    ca_file = f"{sa_dir}/ca.crt"
    ns_file = f"{sa_dir}/namespace"
    host = os.environ.get("KUBERNETES_SERVICE_HOST")
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    if not host or not os.path.isfile(token_file):
        raise MissingEnvError(
            ["k8s"],
            detail="k8s resolver requires an in-cluster service account",
        )
    resolved_ns = namespace
    if not resolved_ns:
        resolved_ns = "default"
        if os.path.isfile(ns_file):
            with open(ns_file, encoding="utf-8") as fh:
                resolved_ns = fh.read().strip() or "default"
    verify: str | bool = ca_file if os.path.isfile(ca_file) else False
    with open(token_file, encoding="utf-8") as fh:
        token = fh.read().strip()
    return token, resolved_ns, verify, f"{host}:{port}"


async def default_k8s_fetch(spec: K8sSpec) -> Mapping[str, str]:
    if not spec.secret:
        raise MissingEnvError(
            ["k8s.secret"],
            detail="k8s requires credentials.k8s.secret",
        )
    token, namespace, verify, authority = await asyncio.to_thread(
        _incluster_sa, spec.namespace
    )
    import httpx

    url = f"https://{authority}/api/v1/namespaces/{namespace}/secrets/{spec.secret}"
    async with httpx.AsyncClient(timeout=10.0, verify=verify) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        body = resp.json()
    encoded = body.get("data") or {}
    decoded: dict[str, str] = {}
    if isinstance(encoded, dict):
        for key, val in encoded.items():
            decoded[str(key)] = base64.b64decode(str(val)).decode()
    if spec.key:
        if spec.key not in decoded:
            raise MissingEnvError(
                [spec.key],
                detail=f"k8s secret '{spec.secret}' missing key '{spec.key}'",
            )
        return {spec.key: decoded[spec.key]}
    return decoded


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


class AwsSmCredentialResolver:
    def __init__(
        self,
        *,
        fetch: AwsFetch | None = None,
        ttl_s: int = 300,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._env = EnvCredentialResolver(env)
        self._fetch = fetch or default_aws_sm_fetch
        self._ttl = ttl_s
        self._cache: dict[tuple[str, str], tuple[float, dict[str, str]]] = {}

    async def resolve(self, name: str, spec: object) -> ResolvedCredentials:
        creds = getattr(spec, "credentials", None)
        provider = getattr(creds, "provider", "env") if creds is not None else "env"
        if provider != "aws_sm":
            return await self._env.resolve(name, spec)
        aws = creds.aws_sm if isinstance(creds, ConnectionCredentials) else AwsSmSpec()
        secret_id = aws.secret_id or name
        key = (name, secret_id)
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return ResolvedCredentials(values=dict(hit[1]))
        try:
            data = dict(await self._fetch(aws))
        except MissingEnvError:
            raise
        except Exception as exc:
            raise MissingEnvError(
                [secret_id], detail=f"aws_sm secret missing at '{secret_id}'"
            ) from exc
        if not data:
            raise MissingEnvError([secret_id], detail=f"aws_sm secret missing at '{secret_id}'")
        self._cache[key] = (now + self._ttl, data)
        return ResolvedCredentials(values=data)


class K8sCredentialResolver:
    def __init__(
        self,
        *,
        fetch: K8sFetch | None = None,
        ttl_s: int = 300,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._env = EnvCredentialResolver(env)
        self._fetch = fetch or default_k8s_fetch
        self._ttl = ttl_s
        self._cache: dict[tuple[str, str], tuple[float, dict[str, str]]] = {}

    async def resolve(self, name: str, spec: object) -> ResolvedCredentials:
        creds = getattr(spec, "credentials", None)
        provider = getattr(creds, "provider", "env") if creds is not None else "env"
        if provider != "k8s":
            return await self._env.resolve(name, spec)
        k8s = creds.k8s if isinstance(creds, ConnectionCredentials) else K8sSpec()
        secret = k8s.secret or name
        key = (name, secret)
        now = time.time()
        hit = self._cache.get(key)
        if hit and hit[0] > now:
            return ResolvedCredentials(values=dict(hit[1]))
        try:
            data = dict(await self._fetch(k8s))
        except MissingEnvError:
            raise
        except Exception as exc:
            raise MissingEnvError([secret], detail=f"k8s secret missing at '{secret}'") from exc
        if not data:
            raise MissingEnvError([secret], detail=f"k8s secret missing at '{secret}'")
        self._cache[key] = (now + self._ttl, data)
        return ResolvedCredentials(values=data)


class CompositeCredentialResolver:
    """Dispatch ``credentials.provider`` to env / vault / aws_sm / k8s."""

    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        *,
        vault_fetch: VaultFetch | None = None,
        aws_fetch: AwsFetch | None = None,
        k8s_fetch: K8sFetch | None = None,
        ttl_s: int = 300,
    ) -> None:
        self._env = EnvCredentialResolver(env)
        self._vault = VaultCredentialResolver(
            fetch=vault_fetch or default_vault_fetch, ttl_s=ttl_s, env=env
        )
        self._aws = AwsSmCredentialResolver(
            fetch=aws_fetch or default_aws_sm_fetch, ttl_s=ttl_s, env=env
        )
        self._k8s = K8sCredentialResolver(
            fetch=k8s_fetch or default_k8s_fetch, ttl_s=ttl_s, env=env
        )

    async def resolve(self, name: str, spec: object) -> ResolvedCredentials:
        creds = getattr(spec, "credentials", None)
        provider = getattr(creds, "provider", "env") if creds is not None else "env"
        if provider == "vault":
            return await self._vault.resolve(name, spec)
        if provider == "aws_sm":
            return await self._aws.resolve(name, spec)
        if provider == "k8s":
            return await self._k8s.resolve(name, spec)
        return await self._env.resolve(name, spec)


def build_credential_resolver(
    env: Mapping[str, str] | None = None,
    *,
    vault_fetch: VaultFetch | None = None,
    aws_fetch: AwsFetch | None = None,
    k8s_fetch: K8sFetch | None = None,
) -> CompositeCredentialResolver:
    return CompositeCredentialResolver(
        env,
        vault_fetch=vault_fetch,
        aws_fetch=aws_fetch,
        k8s_fetch=k8s_fetch,
    )
