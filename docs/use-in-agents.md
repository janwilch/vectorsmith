# Use VectorSmith in an agent

Two paths, one YAML. Hub: [documentation home](README.md) · [Python API](python-api.md) · [integrations](integrations/README.md).

**Python app** — import one function. No MCP subprocess.

```bash
pip install "vectorsmith[qdrant,langchain]"
```

```python
from vectorsmith import load_tools
from langchain.agents import create_agent

tools = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
agent = create_agent("openai:gpt-4.1", tools)
```

**Chat / IDE host** (Claude Desktop, Claude Code, Codex, Cursor) — those products spawn a process. They cannot import Python.

```json
{
  "mcpServers": {
    "invoices": {
      "command": "vectorsmith",
      "args": ["serve", "tools.invoices.yaml", "--name", "invoices"]
    }
  }
}
```

Codex uses TOML instead of JSON. Full copy-paste for every host and framework: **[docs/integrations/](integrations/README.md)**.

## Framework extras

| Extra | Import |
|---|---|
| `vectorsmith[langchain]` | `from vectorsmith import load_tools` |
| `vectorsmith[langgraph]` | same tools; `create_react_agent` / `ToolNode` |
| `vectorsmith[openai-agents]` | `from vectorsmith.openai_agents import load_tools` |
| `vectorsmith[anthropic]` | `from vectorsmith.anthropic import load_tools` |

Any other stack: `pip install "vectorsmith[qdrant]"` then `from vectorsmith import connect` and `await vs.call(name, args)`. That path does not need the LangChain extra.

## While authoring

Write and check the YAML first — **[tools.yaml reference](tools-yaml-reference.md)** (connections, tools, filters, built-ins).

`vectorsmith validate` and `vectorsmith test` check a file before you wire `load_tools` or `serve`.
