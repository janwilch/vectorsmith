# LangChain agent

`pip install vectorsmith[qdrant,langchain]`, write YAML, import `load_tools`.

```python
from vectorsmith import load_tools

tools = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
# pass into LangChain create_agent together with your own @tools
```

Slack (or any other MCP server) stays a normal MCP client. VectorSmith tools are in-process — no `serve` subprocess.

```bash
pip install "vectorsmith[qdrant,langchain]"
pip install -r requirements.txt
export OPENAI_API_KEY=…
python agent.py
```

From this repo, run inside `examples/langchain_agent/` so the script finds the sibling `qdrant_invoices` YAML.

LangGraph, OpenAI Agents, and Anthropic: sibling folders under [`examples/`](../). Hosts (Claude / Codex / Cursor): [docs/integrations/](../../docs/integrations/README.md).
