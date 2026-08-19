"""T3: VectorSmithError attributes and reprs never leak secrets."""

from vectorsmith_core.errors import (
    AuthError,
    BackendUnreachable,
    EmbeddingError,
    ExprError,
    InternalError,
    InvalidArgumentsError,
    MissingEnvError,
    QueryTimeout,
    RateLimited,
    SchemaDriftError,
    TDSValidationError,
    VectorSmithError,
)


def test_base_attrs() -> None:
    err = VectorSmithError("internal", retryable=False, detail="x")
    assert err.code == "internal"
    assert err.retryable is False
    assert err.detail == "x"
    assert "internal" in repr(err)
    assert str(err) == "x"


def test_retryable_subclasses() -> None:
    assert BackendUnreachable().retryable is True
    assert RateLimited().retryable is True
    assert QueryTimeout().retryable is True
    assert AuthError().retryable is False
    assert InvalidArgumentsError().retryable is False
    assert SchemaDriftError().retryable is False
    assert ExprError().retryable is False
    assert EmbeddingError().retryable is False
    assert InternalError().retryable is False


def test_missing_env_lists_all_vars() -> None:
    err = MissingEnvError(["QDRANT_URL", "QDRANT_API_KEY"])
    assert err.vars == ["QDRANT_URL", "QDRANT_API_KEY"]
    assert err.code == "missing_env"
    assert "QDRANT_URL" in err.detail
    assert "QDRANT_API_KEY" in err.detail


def test_tds_validation_keeps_issues() -> None:
    issues = [{"code": "VB2001"}]
    err = TDSValidationError(issues)
    assert err.code == "tds_invalid"
    assert err.issues == issues


def test_repr_has_no_credential_payload() -> None:
    err = AuthError(detail="bad key sk-secretvalue")
    assert "sk-secretvalue" not in repr(err)
    assert "code=" in repr(err)
