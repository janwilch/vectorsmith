"""Anthropic Messages API: YAML tools via ``load_tools``, plus a short tool loop."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import anthropic

from vectorsmith.anthropic import load_tools

HERE = Path(__file__).resolve().parent
MAX_ROUNDS = 8


def _project_dir() -> Path:
    if Path("tools.invoices.yaml").is_file():
        return Path.cwd()
    bundled = HERE.parent / "qdrant_invoices"
    if (bundled / "tools.invoices.yaml").is_file():
        return bundled
    raise SystemExit(
        "No tools.invoices.yaml in this directory. Add your TDS files next to the app."
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "Find overdue Globex invoices and any open critical tickets. "
            "Summarize for a support agent."
        ),
    )
    args = parser.parse_args()
    root = _project_dir()
    env_file = root / ".env" if (root / ".env").is_file() else root / ".env.example"

    vs = load_tools(
        root / "tools.invoices.yaml",
        root / "tools.tickets.yaml",
        env_file=env_file,
    )
    try:
        print(f"tools ({len(vs.tools)}):", ", ".join(vs.names))
        client = anthropic.Anthropic()
        messages: list[dict] = [{"role": "user", "content": args.prompt}]
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        for _ in range(MAX_ROUNDS):
            resp = client.messages.create(
                model=model,
                max_tokens=2048,
                tools=vs.tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                text = "".join(
                    block.text for block in resp.content if block.type == "text"
                )
                print(text)
                return
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                output = await vs.execute(block.name, block.input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    }
                )
            messages.append({"role": "user", "content": results})
        print("stopped after max tool rounds")
    finally:
        await vs.aclose()


if __name__ == "__main__":
    asyncio.run(main())
