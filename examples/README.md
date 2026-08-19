# Examples

Docs hub: [docs/README.md](../docs/README.md). YAML contract: [tools.yaml reference](../docs/tools-yaml-reference.md).

How a user authors VectorSmith tools against their own vector database, then uses them in an agent or over MCP.

Copy [`qdrant_invoices/.env.example`](qdrant_invoices/.env.example) to `.env` and set `QDRANT_URL` to your cluster. The committed example is `http://localhost:6333` only.

## `qdrant_invoices`

Two MCP servers (the `mcpServers` key / `--name` is what Claude Connectors show):

| File | MCP name | Role |
|---|---|---|
| [`tools.invoices.yaml`](qdrant_invoices/tools.invoices.yaml) | `invoices` | Invoice search / lookup / count |
| [`tools.tickets.yaml`](qdrant_invoices/tools.tickets.yaml) | `tickets` | Support-ticket search / lookup / count |
| [`qdrant_invoices/.env.example`](qdrant_invoices/.env.example) | | `QDRANT_URL` for that cluster |
| [`qdrant_invoices/seed_tickets.py`](qdrant_invoices/seed_tickets.py) | | Create `tickets` and upsert 80 sample rows |
| [`qdrant_invoices/validate_tools.py`](qdrant_invoices/validate_tools.py) | | Compile both files (`load_project` only) |

### CLI

From the repo root:

```bash
uv run vectorsmith validate examples/qdrant_invoices/tools.invoices.yaml \
  --env-file examples/qdrant_invoices/.env.example
uv run vectorsmith validate examples/qdrant_invoices/tools.tickets.yaml \
  --env-file examples/qdrant_invoices/.env.example

uv run vectorsmith test examples/qdrant_invoices/tools.invoices.yaml search_invoices \
  --args '{"query":"Globex invoice","limit":3}' \
  --env-file examples/qdrant_invoices/.env.example

# Two processes — two connector names
uv run vectorsmith serve examples/qdrant_invoices/tools.invoices.yaml --name invoices \
  --env-file examples/qdrant_invoices/.env.example
uv run vectorsmith serve examples/qdrant_invoices/tools.tickets.yaml --name tickets \
  --env-file examples/qdrant_invoices/.env.example
```

`load_project()` (authoring API) interpolates the env map you pass, synthesizes builtins, validates, and compiles. The CLI `validate` / `serve` / `test` commands interpolate **only** `--env-file` (they do not merge the process environment).

## Agent frameworks (in-process `load_tools`)

| Directory | Import |
|---|---|
| [`langchain_agent/`](langchain_agent/) | `from vectorsmith import load_tools` + your `@tool`s + optional Slack MCP |
| [`langgraph_agent/`](langgraph_agent/) | `from vectorsmith.langgraph import load_tools` + `create_react_agent` |
| [`openai_agents/`](openai_agents/) | `from vectorsmith.openai_agents import load_tools` + `Agent` / `Runner` |
| [`anthropic_agent/`](anthropic_agent/) | `from vectorsmith.anthropic import load_tools` + Messages API tool loop |

## MCP hosts (Claude, Codex, Cursor)

Copy-paste configs: [`mcp_hosts/`](mcp_hosts/). Full write-ups: [docs/integrations/](../docs/integrations/README.md).

## Alongside other MCP servers

Each VectorSmith `serve` is one `mcpServers` entry. Add filesystem, GitHub, or a second VectorSmith project next to it. Details: [docs/coexistence.md](../docs/coexistence.md).
