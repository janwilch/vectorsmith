"""validate command — static (and optional --live)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vectorsmith_core.api import load_project


def run_validate(
    tools: Path,
    *,
    live: bool = False,
    live_embed: bool = False,
    as_json: bool = False,
    strict: bool = False,
    env_file: Path | None = None,
    enterprise: bool = False,
    profile: str | None = None,
    policy: Path | None = None,
    policy_builtin: str | None = None,
) -> int:
    env = _load_env(env_file)
    try:
        project = load_project(tools, env=env, strict=strict)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    issues = list(project.issues)
    if enterprise or profile == "enterprise":
        from vectorsmith_core.compilepkg.enterprise import enterprise_issues
        from vectorsmith_core.tds.loader import read_source

        raw = read_source(tools)
        issues.extend(
            enterprise_issues(project.tds, raw=raw if isinstance(raw, dict) else None)
        )
    if policy or policy_builtin:
        from vectorsmith_core.policy.eval_policy import eval_policies

        issues.extend(
            eval_policies(
                project.tds,
                policy_path=policy,
                builtin=policy_builtin,
            )
        )
    if live:
        import asyncio

        from vectorsmith_core.api import EnvCredentialResolver
        from vectorsmith_core.execute.engine import Engine

        async def _live() -> list:
            engine = Engine(project, credential_resolver=EnvCredentialResolver(env))
            try:
                return await engine.validate_live(live_embed=live_embed)
            finally:
                await engine.aclose()

        issues = asyncio.run(_live())
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    payload = [i.model_dump() for i in issues]
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for i in issues:
            loc = i.tool or i.path or ""
            print(f"{i.severity.upper()} {i.code} {loc}: {i.message}", file=sys.stderr)
        print(f"{len(project.tools)} tool(s) compiled", file=sys.stderr)
    if errors:
        return 2
    if strict and warnings:
        return 1
    return 0


def _load_env(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out
