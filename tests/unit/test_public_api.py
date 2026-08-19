"""Public package surface is authoring-only; execution stays internal."""

from __future__ import annotations

import vectorsmith_core
import vectorsmith_core.api as api

_EXECUTION = frozenset(
    {
        "Engine",
        "CallContext",
        "ToolResult",
        "EnvCredentialResolver",
        "CredentialResolver",
        "EmbedProvider",
        "HealthStatus",
        "CompiledTool",
        "ResolvedCredentials",
    }
)


def test_package_all_is_authoring_only() -> None:
    public = set(vectorsmith_core.__all__)
    assert public == {
        "ENGINE_VERSION",
        "SUPPORTED_TDS",
        "Issue",
        "Project",
        "ToolDraft",
        "draft_tool",
        "load_project",
        "promote_draft",
    }
    for name in _EXECUTION:
        assert name not in public
        assert not hasattr(vectorsmith_core, name)


def test_engine_not_reexported_from_api() -> None:
    assert "Engine" not in api.__all__
    assert not hasattr(api, "Engine")
