"""vectorsmith migrate — rewrite TDS files between versions."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import yaml

from vectorsmith_core.tds.migrate import migrate_document


def run_migrate(
    tools: Path,
    *,
    from_version: str,
    to_version: str,
    dry_run: bool,
    write: bool,
) -> int:
    if not dry_run and not write:
        print("pass --dry-run or --write", file=sys.stderr)
        return 2
    text = tools.read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        print("tools.yaml root must be a mapping", file=sys.stderr)
        return 2
    try:
        migrated = migrate_document(data, from_version=from_version, to_version=to_version)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    new_text = yaml.safe_dump(migrated, sort_keys=False)
    if dry_run:
        diff = difflib.unified_diff(
            text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(tools),
            tofile=f"{tools} (v{to_version})",
        )
        sys.stdout.writelines(diff)
        return 0
    tools.write_text(new_text)
    print(f"wrote {tools} as tds_version {to_version}", file=sys.stderr)
    return 0
