# Other frameworks

Hub: [documentation home](../index.md) · [Python API](../python-api.md).

Anything that can call an async function with a JSON object can use `connect`. You do not need a first-party adapter. Install the store extra (`vectorsmith[qdrant]`); you do **not** need `langchain`.

```python
from vectorsmith import connect

vs = connect("tools.invoices.yaml", "tools.tickets.yaml")
try:
    print(vs.names)
    rows = await vs.call("search_invoices", {"query": "Globex", "limit": 3})
    # wrap vs.call / vs.schemas in your framework's Tool type
finally:
    await vs.aclose()
```

`vs.schemas` is MCP shape (`name`, `description`, `inputSchema`). `vs.as_anthropic()` remaps `inputSchema` → `input_schema`.

## LlamaIndex

```python
from llama_index.core.tools import FunctionTool
from vectorsmith import connect

vs = connect("tools.yaml")

def _wrap(name: str):
    async def _fn(**kwargs):
        return await vs.call(name, kwargs)
    return _fn

tools = [
    FunctionTool.from_defaults(
        async_fn=_wrap(s["name"]),
        name=s["name"],
        description=s.get("description") or s["name"],
    )
    for s in vs.schemas
]
```

## CrewAI

CrewAI agents accept LangChain tools. Use [LangChain `load_tools`](langchain.md) and pass the list into the CrewAI agent.

## Official MCP Python client

If you would rather not import VectorSmith in the agent process, run `vectorsmith serve` and attach with the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) or `langchain-mcp-adapters` — same as Slack or GitHub.
