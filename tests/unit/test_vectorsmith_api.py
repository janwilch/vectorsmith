"""Public vectorsmith package surface."""

from __future__ import annotations

import vectorsmith


def test_package_all() -> None:
    assert set(vectorsmith.__all__) == {"BoundTools", "Toolset", "connect", "load_tools"}
    assert callable(vectorsmith.connect)
    assert callable(vectorsmith.load_tools)
    assert vectorsmith.BoundTools is not None
    assert vectorsmith.Toolset is not None
