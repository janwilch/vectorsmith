# LangChain

Hub: [documentation home](../README.md) · [Python API](../python-api.md) · [Integrations](README.md).

In-process. No `vectorsmith serve` subprocess.

```bash
pip install "vectorsmith[qdrant,langchain]"
```

```python
from vectorsmith import load_tools
from langchain.agents import create_agent

tools = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
try:
    agent = create_agent("openai:gpt-4.1", tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
finally:
    await tools.aclose()
```

`load_tools` compiles the YAML and returns LangChain `StructuredTool`s (requires the `langchain` extra / `langchain-core`). Mix them with your own `@tool`s and with MCP clients (`langchain-mcp-adapters`) for Slack/GitHub.

Worked sample: [`examples/langchain_agent/`](../../examples/langchain_agent/).

`from vectorsmith.langchain import load_tools` is the same function.

LangGraph uses these tools unchanged — [LangGraph](langgraph.md).
