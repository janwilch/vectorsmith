"""Validate invoice and ticket TDS files (authoring only)."""

from __future__ import annotations

import sys
from pathlib import Path

from vectorsmith_core import load_project

HERE = Path(__file__).resolve().parent
FILES = [HERE / "tools.invoices.yaml", HERE / "tools.tickets.yaml"]
ENV_FILE = HERE / ".env" if (HERE / ".env").exists() else HERE / ".env.example"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def print_issues(project) -> tuple[int, int]:
    errors = [i for i in project.issues if i.severity == "error"]
    warnings = [i for i in project.issues if i.severity == "warning"]
    if not project.issues:
        print("validation: no issues")
    for issue in project.issues:
        loc = issue.tool or issue.path or ""
        print(f"{issue.severity.upper()} {issue.code} {loc}: {issue.message}")
    return len(errors), len(warnings)


def main() -> int:
    env = load_env(ENV_FILE)
    print(f"env: {ENV_FILE} (QDRANT_URL={env.get('QDRANT_URL')})")
    worst = 0
    for tools in FILES:
        print(f"\n=== {tools.name} ===")
        project = load_project(tools, env=env)
        n_err, n_warn = print_issues(project)
        print(f"compiled {len(project.tools)} tool(s):")
        for schema in project.mcp_tool_schemas():
            kind = "builtin" if project.tools[schema["name"]].is_synthetic else "user"
            print(f"  - {schema['name']} [{kind}]")
        if n_err:
            print(f"validation failed: {n_err} error(s), {n_warn} warning(s)")
            worst = 2
        else:
            print(f"validation passed ({n_warn} warning(s))")
    return worst


if __name__ == "__main__":
    sys.exit(main())
