"""Stable error taxonomy. Every exception leaving core subclasses VectorSmithError."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class VectorSmithError(Exception):
    """Base error. ``code`` is machine-stable; ``detail`` is one actionable line."""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        detail: str = "",
    ) -> None:
        self.code = code
        self.retryable = retryable
        self.detail = detail
        super().__init__(detail or code)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, retryable={self.retryable})"
        )


class TDSValidationError(VectorSmithError):
    """TDS failed validation. ``issues`` is the collected Issue list."""

    def __init__(self, issues: Sequence[object], *, detail: str = "") -> None:
        self.issues = list(issues)
        super().__init__(
            "tds_invalid",
            retryable=False,
            detail=detail or f"{len(self.issues)} validation issue(s)",
        )


class MissingEnvError(VectorSmithError):
    """One or more ``${VAR}`` references under connections were unset."""

    def __init__(self, vars: Sequence[str], *, detail: str = "") -> None:  # noqa: A002
        self.vars = list(vars)
        super().__init__(
            "missing_env",
            retryable=False,
            detail=detail or f"missing environment variables: {', '.join(self.vars)}",
        )


class AuthError(VectorSmithError):
    def __init__(self, *, detail: str = "authentication failed") -> None:
        super().__init__("auth_error", retryable=False, detail=detail)


class BackendUnreachable(VectorSmithError):
    def __init__(self, *, detail: str = "backend unreachable") -> None:
        super().__init__("backend_unreachable", retryable=True, detail=detail)


class InvalidArgumentsError(VectorSmithError):
    def __init__(
        self, *, detail: str = "invalid arguments", code: str = "invalid_arguments"
    ) -> None:
        super().__init__(code, retryable=False, detail=detail)


class SchemaDriftError(VectorSmithError):
    def __init__(self, *, detail: str = "schema drift detected") -> None:
        super().__init__("schema_drift", retryable=False, detail=detail)


class RateLimited(VectorSmithError):
    def __init__(
        self, *, detail: str = "rate limited", retry_after_s: int = 60
    ) -> None:
        self.retry_after_s = retry_after_s
        super().__init__("rate_limited", retryable=True, detail=detail)


class QueryTimeout(VectorSmithError):
    def __init__(self, *, detail: str = "query timed out") -> None:
        super().__init__("timeout", retryable=True, detail=detail)


class ExprError(VectorSmithError):
    def __init__(self, *, detail: str = "expression error") -> None:
        super().__init__("expr_error", retryable=False, detail=detail)


class EmbeddingError(VectorSmithError):
    def __init__(self, *, detail: str = "embedding failed") -> None:
        super().__init__("embedding_error", retryable=False, detail=detail)


class InternalError(VectorSmithError):
    def __init__(self, *, detail: str = "internal error") -> None:
        super().__init__("internal", retryable=False, detail=detail)
