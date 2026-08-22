"""Build an ``AuthProvider`` from CLI flags + TDS ``security.auth``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vectorsmith_cli.http.auth.api_key import APIKeyProvider
from vectorsmith_cli.http.auth.builtin import BuiltinOAuthProvider
from vectorsmith_cli.http.auth.jwt import JWTProvider
from vectorsmith_cli.http.auth.none import NoneAuthProvider
from vectorsmith_core.tds.models import APIKeyAuthConfig, AuthConfig, JWTAuthConfig


def merge_jwt_cfg(
    yaml_cfg: JWTAuthConfig,
    *,
    issuer: str | None,
    audience: str | None,
    jwks_url: str | None,
) -> JWTAuthConfig:
    data = yaml_cfg.model_dump()
    if issuer:
        data["issuer"] = issuer
    if audience:
        data["audience"] = audience
    if jwks_url:
        data["jwks_url"] = jwks_url
    return JWTAuthConfig.model_validate(data)


def merge_api_key_cfg(yaml_cfg: APIKeyAuthConfig, *, keys_file: Path | None) -> APIKeyAuthConfig:
    data = yaml_cfg.model_dump()
    if keys_file is not None:
        data["keys_file"] = str(keys_file)
    return APIKeyAuthConfig.model_validate(data)


def build_auth_provider(
    mode: str,
    *,
    store: Any,
    auth_cfg: AuthConfig,
    jwt_cfg: JWTAuthConfig,
    api_key_cfg: APIKeyAuthConfig,
    jwks: dict[str, Any] | None = None,
) -> Any:
    _ = auth_cfg
    if mode == "none":
        return NoneAuthProvider()
    if mode == "jwt":
        return JWTProvider(jwt_cfg, jwks=jwks)
    if mode == "api_key":
        return APIKeyProvider.from_file(api_key_cfg)
    return BuiltinOAuthProvider(store)
