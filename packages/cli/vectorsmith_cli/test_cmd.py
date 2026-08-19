"""test — smoke-test one compiled tool without serving MCP.

Not an application API. Agents consume tools over MCP via ``vectorsmith serve``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from vectorsmith_cli.validate_cmd import _load_env
from vectorsmith_core.api import CallContext, EnvCredentialResolver, load_project
from vectorsmith_core.embed.provider import FastEmbedProvider
from vectorsmith_core.execute.engine import Engine


def run_test(
    tools: Path,
    tool: str,
    args_json: str,
    *,
    show_plan: bool = False,
    env_file: Path | None = None,
) -> int:
    env = _load_env(env_file)
    project = load_project(tools, env=env)
    errors = [i for i in project.issues if i.severity == "error"]
    if errors:
        for i in errors:
            print(f"{i.code}: {i.message}", file=sys.stderr)
        return 2
    args = json.loads(args_json)
    compiled = project.tools.get(tool)
    if compiled is None:
        print(f"unknown tool {tool}", file=sys.stderr)
        return 2
    if show_plan and compiled.plan:
        print(json.dumps(compiled.mcp_schema, indent=2), file=sys.stderr)
        plan_meta = {
            "kind": compiled.plan.kind,
            "collection": compiled.plan.collection,
            "mode": compiled.plan.mode,
        }
        print(json.dumps(plan_meta), file=sys.stderr)

    async def _go() -> int:
        embed = None
        try:
            embed = FastEmbedProvider()
        except Exception:
            embed = None
        engine = Engine(
            project, credential_resolver=EnvCredentialResolver(env), embed_provider=embed
        )
        try:
            result = await engine.call(
                tool, args, ctx=CallContext(request_id=str(uuid.uuid4())), debug=show_plan
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(json.dumps(result.model_dump(), default=str, indent=2)[:20000])
        return 0

    return asyncio.run(_go())
