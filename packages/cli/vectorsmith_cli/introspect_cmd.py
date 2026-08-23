"""introspect command."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from vectorsmith_cli.validate_cmd import _load_env
from vectorsmith_core.api import load_project
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.security.credentials import build_credential_resolver


def run_introspect(
    tools: Path,
    *,
    connection: str,
    out: Path,
    collections: str | None,
    redact_examples: bool,
    audit: bool,
    env_file: Path | None,
) -> int:
    env = _load_env(env_file)
    project = load_project(tools, env=env)

    async def _go() -> dict:
        engine = Engine(project, credential_resolver=build_credential_resolver(env))
        cols = collections.split(",") if collections else None
        return await engine.introspect(
            connection, collections=cols, redact_examples=redact_examples
        )

    try:
        report = asyncio.run(_go())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 3
    text = json.dumps(report, indent=2, default=str)
    if audit:
        print(text)
        return 0
    out.write_text(text)
    print(f"wrote {out}", file=sys.stderr)
    return 0
