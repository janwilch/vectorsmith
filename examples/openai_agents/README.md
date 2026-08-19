# OpenAI Agents SDK

`pip install vectorsmith[qdrant,openai-agents]`, write YAML, import `load_tools`.

```python
from vectorsmith.openai_agents import load_tools
from agents import Agent, Runner

tools = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
agent = Agent(name="Support", tools=tools)
```

This is **in-process** (no `vectorsmith serve`). For the **Codex CLI / IDE** (an MCP host), use [OpenAI Codex](../../docs/integrations/openai-codex.md) instead.

```bash
pip install "vectorsmith[qdrant,openai-agents]"
pip install -r requirements.txt
export OPENAI_API_KEY=…
python agent.py
```

From this repo, run inside `examples/openai_agents/` so the script finds the sibling `qdrant_invoices` YAML.
