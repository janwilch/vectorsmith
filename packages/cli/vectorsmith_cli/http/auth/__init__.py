"""HTTP request identity and auth providers."""

from vectorsmith_cli.http.auth.context import call_context_from_request
from vectorsmith_cli.http.auth.resolve import build_auth_provider

__all__ = ["build_auth_provider", "call_context_from_request"]
