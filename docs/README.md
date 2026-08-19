<div align="center">

<img src="assets/mark.svg" width="64" height="64" alt="VectorSmith"/>

# VectorSmith documentation

Your vector database, as typed tools. Start here, then pick a path.

</div>

**Start here:** [Getting started](getting-started.md) — clone, validate, test one tool, serve MCP, or `load_tools` in Python.

---

## Find a page

### Tutorials

| | |
|---|---|
| [Getting started](getting-started.md) | Install, write YAML, prove a tool works |
| [Claude Desktop](quickstart-desktop.md) | Connectors, sandbox, `--watch` |
| [HTTP / claude.ai](quickstart-selfhost.md) | `serve --http`, OAuth, `/mcp` |

### How-to

| | |
|---|---|
| [Use in an agent](use-in-agents.md) | `load_tools` vs `serve` |
| [Integrations](integrations/README.md) | Claude, Codex, Cursor, LangChain, LangGraph, Agents SDK, Anthropic |
| [Next to other MCP servers](coexistence.md) | Slack, GitHub, filesystem, vendor MCP |
| [Deploy](../deploy-templates/README.md) | Docker, Kubernetes, Cloud Run, Fly |

### Reference

| | |
|---|---|
| [tools.yaml](tools-yaml-reference.md) | Every field, operators, pipelines, `VBxxxx` |
| [CLI](cli.md) | `init` · `validate` · `serve` · `test` · `introspect` · `drafts` · `approve` · `auth` |
| [Python API](python-api.md) | `connect`, `load_tools`, extras, return envelope |

### Explanation

| | |
|---|---|
| [How it is put together](architecture.md) | Compile pipeline, two doors, what stays private |
| [FAQ](faq.md) | Desktop disconnects, env interpolation, HTTP auth, hybrids |
| [Repository map](repository.md) | What each top-level path is for |

### Examples in the repo

[examples/README.md](../examples/README.md) — invoice + ticket YAML, four agent apps, MCP host configs.

---

## Choose your install extra

```bash
pip install "vectorsmith[qdrant]"              # CLI + connect()
pip install "vectorsmith[qdrant,langchain]"    # + load_tools for LangChain / LangGraph
pip install "vectorsmith[qdrant,langgraph]"
pip install "vectorsmith[qdrant,openai-agents]"
pip install "vectorsmith[qdrant,anthropic]"
```

Store extras: `qdrant` · `pgvector` · `chroma` · `pinecone` · `weaviate` · `milvus`.

---

## Project docs (repo root)

[Repository map](repository.md) · [Support](../SUPPORT.md) · [Contributing](../CONTRIBUTING.md) · [Security](../SECURITY.md) · [Changelog](../CHANGELOG.md) · [Code of conduct](../CODE_OF_CONDUCT.md) · [License](../LICENSE)
