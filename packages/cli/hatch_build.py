"""Ship ``vectorsmith_core`` inside the ``vectorsmith`` wheel (not a second PyPI project)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del version
        root = Path(self.root)
        local = root / "vectorsmith_core"
        sibling = root.parent / "core" / "vectorsmith_core"
        if (local / "__init__.py").is_file():
            src = local
        elif (sibling / "__init__.py").is_file():
            src = sibling
        else:
            raise RuntimeError(
                "vectorsmith_core not found at ./vectorsmith_core or ../core/vectorsmith_core"
            )
        build_data.setdefault("force_include", {})
        build_data["force_include"][str(src)] = "vectorsmith_core"
