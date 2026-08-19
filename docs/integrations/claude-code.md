# Claude Code

Hub: [documentation home](../index.md) · [Integrations](README.md).

Claude Code is a **different** MCP host from Claude Desktop. It does **not** read `claude_desktop_config.json`.

| Scope | File | Who sees it |
|---|---|---|
| Project (share with the team) | `.mcp.json` at the repo root | Everyone who clones the repo |
| User (all your projects) | `~/.claude.json` → top-level `mcpServers` | Only you |
| Local (this project, private) | `~/.claude.json` under the project entry | Only you, this directory |

`~/.claude/settings.json` is **not** the MCP file.

## Fast path

`vectorsmith` must be on your `PATH` (`pip install "vectorsmith[qdrant]"`).

```bash
claude mcp add invoices --scope project -- \
  vectorsmith serve /absolute/path/tools.invoices.yaml \
  --env-file /absolute/path/.env --name invoices

claude mcp add tickets --scope project -- \
  vectorsmith serve /absolute/path/tools.tickets.yaml \
  --env-file /absolute/path/.env --name tickets
```

Already configured Desktop on macOS/WSL:

```bash
claude mcp add-from-claude-desktop
```

## Project `.mcp.json`

```json
{
  "mcpServers": {
    "invoices": {
      "type": "stdio",
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
      "type": "stdio",
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

`${VAR}` in `tools.yaml` is filled from `--env-file` (see args above), not from a host `env` map. Keep secrets in that file or the environment **inside** the env file.

## HTTP (shared / remote)

```bash
vectorsmith serve tools.invoices.yaml --name invoices \
  --http 127.0.0.1:8080 --auth none
```

```bash
claude mcp add --transport http invoices http://127.0.0.1:8080/mcp
```

`--auth none` is localhost-only. The MCP path is `/mcp`. HTTP `serve` does not watch/reload YAML. Public URL: [self-host](../quickstart-selfhost.md).

## In-app Claude (Python)

If you are calling the Anthropic API yourself, do not use `serve`. Use [Anthropic Messages](anthropic.md).
