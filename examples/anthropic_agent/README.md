# Anthropic Messages API

`pip install vectorsmith[qdrant,anthropic]`, write YAML, import `load_tools`. Pass `vs.tools` into `messages.create` and dispatch `tool_use` with `vs.execute`.

```python
from vectorsmith.anthropic import load_tools

vs = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
resp = client.messages.create(model="claude-sonnet-4-20250514", tools=vs.tools, messages=…)
```

This is **in-process**. For **Claude Desktop** or **Claude Code**, those hosts spawn `vectorsmith serve` — see [Claude Desktop](../../docs/integrations/claude-desktop.md) and [Claude Code](../../docs/integrations/claude-code.md).

```bash
pip install "vectorsmith[qdrant,anthropic]"
pip install -r requirements.txt
export ANTHROPIC_API_KEY=…
python agent.py
```

From this repo, run inside `examples/anthropic_agent/` so the script finds the sibling `qdrant_invoices` YAML.
