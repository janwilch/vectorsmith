"""LangGraph app: YAML tools via ``load_tools``, plus your own tools.

Same VectorSmith API as the LangChain example — LangGraph consumes LangChain tools.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from vectorsmith.langgraph import load_tools

HERE = Path(__file__).resolve().parent


def _project_dir() -> Path:
    if Path("tools.invoices.yaml").is_file():
        return Path.cwd()
    bundled = HERE.parent / "qdrant_invoices"
    if (bundled / "tools.invoices.yaml").is_file():
        return bundled
    raise SystemExit(
        "No tools.invoices.yaml in this directory. Add your TDS files next to the app."
    )


_CRM = {
    "globex": {"account_id": "ACC-100", "csm": "Priya", "plan": "enterprise"},
    "acme": {"account_id": "ACC-001", "csm": "Noah", "plan": "growth"},
}


@tool
def get_current_user() -> dict:
    """Return the signed-in support agent. Call first when the user is 'me'."""
    return {"email": "agent@example.com", "role": "support", "team": "billing"}


@tool
def lookup_crm_account(name: str) -> dict:
    """Look up an internal CRM account by company name (globex, acme, …)."""
    key = name.strip().lower()
    row = _CRM.get(key)
    if row is None:
        return {"found": False, "name": name}
    return {"found": True, "name": name, **row}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "Look up Globex in the CRM, then find their overdue invoices "
            "and any open critical tickets. Summarize for the current agent."
        ),
    )
    args = parser.parse_args()
    root = _project_dir()
    env_file = root / ".env" if (root / ".env").is_file() else root / ".env.example"

    vs_tools = load_tools(
        root / "tools.invoices.yaml",
        root / "tools.tickets.yaml",
        env_file=env_file,
    )
    try:
        tools = [get_current_user, lookup_crm_account, *vs_tools]
        print(f"tools ({len(tools)}):", ", ".join(t.name for t in tools))
        model = init_chat_model(os.environ.get("LANGCHAIN_MODEL", "openai:gpt-4.1"))
        agent = create_react_agent(model, tools)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": args.prompt}]}
        )
        messages = result.get("messages") or []
        if messages:
            print(messages[-1].content)
    finally:
        await vs_tools.aclose()


if __name__ == "__main__":
    asyncio.run(main())
