# LangGraph agent

`pip install vectorsmith[qdrant,langgraph]`, write YAML, import `load_tools`. LangGraph uses the same LangChain tools as [`../langchain_agent`](../langchain_agent/).

```python
from vectorsmith.langgraph import load_tools
from langgraph.prebuilt import create_react_agent

tools = load_tools("tools.invoices.yaml", "tools.tickets.yaml")
agent = create_react_agent(model, tools)
```

`from vectorsmith import load_tools` is the same function.

```bash
pip install "vectorsmith[qdrant,langgraph]"
pip install -r requirements.txt
export OPENAI_API_KEY=…
python agent.py
```

From this repo, run inside `examples/langgraph_agent/` so the script finds the sibling `qdrant_invoices` YAML.

Docs: [LangGraph integration](../../docs/integrations/langgraph.md).
