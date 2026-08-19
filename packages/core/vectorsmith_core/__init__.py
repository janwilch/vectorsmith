"""VectorSmith authoring API.

Compile a ``tools.yaml`` (or dict) into a Project. In-app agents use
``from vectorsmith import load_tools``. Claude Desktop uses ``vectorsmith serve``.
"""

from vectorsmith_core.api import (
    Issue,
    Project,
    ToolDraft,
    draft_tool,
    load_project,
    promote_draft,
)
from vectorsmith_core.version import ENGINE_VERSION, SUPPORTED_TDS

__all__ = [
    "ENGINE_VERSION",
    "SUPPORTED_TDS",
    "Issue",
    "Project",
    "ToolDraft",
    "draft_tool",
    "load_project",
    "promote_draft",
]
