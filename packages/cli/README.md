# vectorsmith

Install this package. Write a `tools.yaml`. Use `load_tools` in Python or `vectorsmith serve` as an MCP server.

```bash
pip install "vectorsmith[qdrant,langchain]"
```

```python
from vectorsmith import load_tools

tools = load_tools("tools.yaml")
```

See the repository `README.md` and `docs/` for integrations and the YAML reference.
