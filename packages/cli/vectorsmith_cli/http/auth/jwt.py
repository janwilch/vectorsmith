"""Validate Bearer JWTs against a JWKS (RS256 / ES256)."""

from __future__ import annotations

import uuid
from typing import Any

from starlette.requests import Request

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import AuthError
from vectorsmith_core.tds.models import JWTAuthConfig


def _jwt_mod() -> Any:
    try:
        import jwt
    except ImportError as exc:
        raise AuthError(
            detail="jwt extra not installed: pip install 'vectorsmith[auth-jwt]'"
        ) from exc
    return jwt


class JWTProvider:
    def __init__(
        self,
        cfg: JWTAuthConfig,
        *,
        jwks: dict[str, Any] | None = None,
    ) -> None:
        self.cfg = cfg
        self._jwks = jwks
        self._jwk_client: Any = None

    def _key(self, token: str) -> Any:
        jwt = _jwt_mod()
        if self._jwks is not None:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            for item in self._jwks.get("keys") or []:
                if kid is None or item.get("kid") == kid:
                    return jwt.PyJWK.from_dict(item).key
            raise AuthError(detail="jwt kid not found in JWKS")
        if not self.cfg.jwks_url:
            raise AuthError(detail="jwks_url is required for jwt auth")
        if self._jwk_client is None:
            self._jwk_client = jwt.PyJWKClient(self.cfg.jwks_url)
        return self._jwk_client.get_signing_key_from_jwt(token).key

    async def authenticate(self, request: Request) -> CallContext:
        jwt = _jwt_mod()
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else ""
        if not token:
            raise AuthError(detail="missing bearer token")
        try:
            payload = jwt.decode(
                token,
                self._key(token),
                algorithms=list(self.cfg.algorithms or ["RS256"]),
                audience=self.cfg.audience,
                issuer=self.cfg.issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError(detail="token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError(detail="invalid token") from exc
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError(detail="invalid token") from exc
        if not isinstance(payload, dict):
            raise AuthError(detail="invalid token")
        prefix = self.cfg.claims_prefix or ""
        claims = {
            (str(k)[len(prefix) :] if prefix and str(k).startswith(prefix) else str(k)): v
            for k, v in payload.items()
        }
        principal = claims.get(self.cfg.principal_claim)
        return CallContext(
            request_id=str(uuid.uuid4()),
            principal=str(principal) if principal is not None else None,
            claims=claims,
        )

    async def health(self) -> bool:
        if self._jwks is not None:
            return bool(self._jwks.get("keys"))
        if not self.cfg.jwks_url:
            return False
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(self.cfg.jwks_url)
                resp.raise_for_status()
                data = resp.json()
            return bool(isinstance(data, dict) and data.get("keys"))
        except Exception:
            return False
