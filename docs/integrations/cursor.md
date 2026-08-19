# Cursor

Hub: [documentation home](../index.md) · [Integrations](README.md).

Cursor is an MCP host. It spawns `vectorsmith serve` the same way Claude Desktop does. It does **not** import Python.

## Project config

`.cursor/mcp.json` in the repo (or Cursor Settings → MCP):

```json
{
  "mcpServers": {
    "invoices": {
      "command": "vectorsmith",
      "args": [
        "serve",
        "examples/qdrant_invoices/tools.invoices.yaml",
        "--env-file",
        "examples/qdrant_invoices/.env.example",
        "--name",
        "invoices"
      ]
    },
    "tickets": {
      "command": "vectorsmith",
      "args": [
        "serve",
        "examples/qdrant_invoices/tools.tickets.yaml",
        "--env-file",
        "examples/qdrant_invoices/.env.example",
        "--name",
        "tickets"
      ]
    }
  }
}
```

`vectorsmith` must be on the `PATH` the IDE uses (`pip install "vectorsmith[qdrant]"` in that environment, or an absolute path to the binary). Relative YAML paths resolve against the workspace. `${VAR}` in `tools.yaml` is filled from `--env-file`, not from Cursor's `env` map.

## Next to other servers

Add filesystem, GitHub, Slack as extra `mcpServers` keys. See [coexistence](../coexistence.md).
