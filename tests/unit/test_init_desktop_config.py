"""init --print-desktop-config uses the user-chosen MCP name."""

from __future__ import annotations

import json
from pathlib import Path

from vectorsmith_cli.init_cmd import run_init


def test_print_desktop_config_default_name(tmp_path: Path, capsys) -> None:
    run_init(tmp_path, print_desktop_config=True)
    cfg = json.loads(capsys.readouterr().out)
    assert "VectorSmith" in cfg["mcpServers"]
    args = cfg["mcpServers"]["VectorSmith"]["args"]
    assert args[-2:] == ["--name", "VectorSmith"]


def test_print_desktop_config_custom_name(tmp_path: Path, capsys) -> None:
    run_init(tmp_path, print_desktop_config=True, name="invoices")
    cfg = json.loads(capsys.readouterr().out)
    assert "invoices" in cfg["mcpServers"]
    assert "VectorSmith" not in cfg["mcpServers"]
    assert cfg["mcpServers"]["invoices"]["args"][-1] == "invoices"
