# VectorSmith

**Your vector database, forged into tools an agent can actually use.**

Write a `tools.yaml`. VectorSmith compiles it into typed, tenant-guarded tools — then you either import them in Python or serve them over MCP.

```bash
pip install "vectorsmith[qdrant]"
```

[Get started](getting-started.md){ .md-button .md-button--primary }
[tools.yaml reference](tools-yaml-reference.md){ .md-button }

---

## Two doors, one YAML

| You are building… | Use |
|---|---|
| A **Python agent** (LangChain, LangGraph, OpenAI Agents, Anthropic SDK) | [`load_tools` / `connect`](python-api.md) |
| A **chat / IDE host** (Claude Desktop, Claude Code, Codex, Cursor) | [`vectorsmith serve`](cli.md) as MCP |

Same file either way. The agent never sees the store URL, the API key, or hidden tenant filters.

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
| [Deploy templates](https://github.com/kjgpta/vectorsmith/blob/main/deploy-templates/README.md) | Docker, Kubernetes, Cloud Run, Fly |

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

Examples in the repo: [invoice + ticket YAML, agent apps, MCP host configs](https://github.com/kjgpta/vectorsmith/tree/main/examples).

---

## Install extras

```bash
pip install "vectorsmith[qdrant]"              # CLI + connect()
pip install "vectorsmith[qdrant,langchain]"    # + load_tools for LangChain / LangGraph
pip install "vectorsmith[qdrant,langgraph]"
pip install "vectorsmith[qdrant,openai-agents]"
pip install "vectorsmith[qdrant,anthropic]"
```

Store extras: `qdrant` · `pgvector` · `chroma` · `pinecone` · `weaviate` · `milvus`.

---

## Status

**0.1.0.** Read-only tools from YAML. Application code uses `from vectorsmith import load_tools` or `connect` — do not import `Engine`.

Source: [github.com/kjgpta/vectorsmith](https://github.com/kjgpta/vectorsmith).
