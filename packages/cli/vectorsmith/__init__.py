"""VectorSmith application API.

In-process (LangChain, LangGraph, OpenAI Agents, Anthropic SDK)::

    from vectorsmith import load_tools   # LangChain / LangGraph
    from vectorsmith import connect      # call() or .as_openai_agents() / .as_anthropic()

MCP hosts (Claude Desktop, Claude Code, Codex, Cursor)::

    vectorsmith serve tools.yaml --name invoices
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vectorsmith.runtime import BoundTools, connect

if TYPE_CHECKING:
    from vectorsmith.langchain_tools import Toolset
    from vectorsmith.langchain_tools import load_tools as load_tools

__all__ = ["BoundTools", "Toolset", "connect", "load_tools"]


def __getattr__(name: str) -> Any:
    if name in {"load_tools", "Toolset"}:
        from vectorsmith.langchain_tools import Toolset, load_tools

        return {"load_tools": load_tools, "Toolset": Toolset}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
