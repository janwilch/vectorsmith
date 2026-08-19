# Using VectorSmith next to other MCP servers

Hub: [documentation home](index.md) · [Integrations](integrations/README.md).

VectorSmith is **one MCP server**. Claude Desktop, Claude Code, Cursor, Codex, and claude.ai all attach **many** servers at once. Tools from every server show up in the same tool list. The host picks among them by name and description.

Python agents that `import vectorsmith` do not go through this file — they call `load_tools` in-process. Host-specific configs: [integrations](integrations/README.md).

You do **not** merge VectorSmith into another server, and you do **not** need a gateway for this.

Per-host files: [Claude Desktop](integrations/claude-desktop.md), [Claude Code](integrations/claude-code.md), [Codex](integrations/openai-codex.md), [Cursor](integrations/cursor.md).

## Claude Desktop / Cursor

Each key under `mcpServers` is the name **you** choose (Claude/Cursor/SDK show it). Default `VectorSmith`; use another key plus `serve --name` if you run more than one project.

```json
{
  "mcpServers": {
    "invoices": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/repo",
        "vectorsmith",
        "serve",
        "/absolute/path/to/repo/examples/qdrant_invoices/tools.invoices.yaml",
        "--env-file",
        "/absolute/path/to/repo/examples/qdrant_invoices/.env.example",
        "--name",
        "invoices"
      ]
    },
    "tickets": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/repo",
        "vectorsmith",
        "serve",
        "/absolute/path/to/repo/examples/qdrant_invoices/tools.tickets.yaml",
        "--env-file",
        "/absolute/path/to/repo/examples/qdrant_invoices/.env.example",
        "--name",
        "tickets"
      ]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/you/docs"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "…" }
    }
  }
}
```

After a restart, Claude can call `search_invoices` (VectorSmith) and `read_file` (filesystem) in the same turn.

Print a starter block:

```bash
uv run vectorsmith init ./demo --print-desktop-config --name VectorSmith
```

That snippet already includes a second server (`filesystem`) so the multi-server shape is obvious.

## What Claude sees

| Source | Examples | Typical job |
|---|---|---|
| VectorSmith (`invoices` / `tickets`) | `search_invoices`, `search_tickets` | Guarded **read** over *your* vector/table store |
| Official Qdrant / Pinecone / vendor MCP | collection admin, upsert, delete | Writes and cluster ops — **not** what VectorSmith does |
| Filesystem / GitHub / Slack / … | `read_file`, `create_issue` | Everything that is not the vector DB |

Keep descriptions specific (`Use when the user asks about invoices…`) so Claude does not send billing questions to `read_file`.

## Official vendor MCP vs VectorSmith

Run **both** if you want:

- VectorSmith for tenant-scoped, approved search tools
- The vendor server for create-collection / upsert / snapshots

Do not give Claude write tools on the same data unless you intend that. VectorSmith tools are read-only.

## claude.ai (HTTP)

Self-host VectorSmith (`serve --http --auth builtin --public-url https://…`) and add it as a **custom connector**. Add other connectors the same way. Each connector is still a separate MCP server; Claude merges their tools.

`--auth none` is localhost-only (exit 3 off-loopback). HTTP `serve` does not `--watch`.

## Same store, two connections

Multiple **stores** can live in one YAML (`connections.main` + `connections.ops_db`). That is still **one** VectorSmith MCP server. Two YAMLs with two `serve --name` processes are **two** connectors (this example: `invoices` and `tickets`). Other products stay as other `mcpServers` entries.

## Name collisions

If two servers expose `search`, Claude may pick the wrong one. Rename the VectorSmith connection (`invoices_qdrant` → tools `search_invoices_qdrant`) or turn off overlapping builtins.
