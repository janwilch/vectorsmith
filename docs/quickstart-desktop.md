# Desktop quickstart

Hub: [documentation home](index.md) · [Claude Desktop](integrations/claude-desktop.md) · [FAQ](faq.md).

VectorSmith is the library. This example is two projects — invoices and tickets — under [`examples/qdrant_invoices`](https://github.com/kjgpta/vectorsmith/tree/main/examples/qdrant_invoices).

--8<-- "docs/includes/demo-video-root.md"

```bash
uv sync
uv run vectorsmith validate examples/qdrant_invoices/tools.invoices.yaml \
  --env-file examples/qdrant_invoices/.env.example
uv run vectorsmith validate examples/qdrant_invoices/tools.tickets.yaml \
  --env-file examples/qdrant_invoices/.env.example
uv run vectorsmith init ./demo --print-desktop-config --name invoices
```

Paste into Claude Desktop → Settings → Developer → Edit config. Each `mcpServers` key is the connector name. This example uses `invoices` and `tickets`:

```json
{
  "mcpServers": {
    "invoices": {
      "command": "/path/to/venv/bin/vectorsmith",
      "args": [
        "serve",
        "/path/to/repo/examples/qdrant_invoices/tools.invoices.yaml",
        "--env-file",
        "/path/to/repo/examples/qdrant_invoices/.env.example",
        "--name",
        "invoices"
      ],
      "cwd": "/path/to/repo/examples/qdrant_invoices"
    },
    "tickets": {
      "command": "/path/to/venv/bin/vectorsmith",
      "args": [
        "serve",
        "/path/to/repo/examples/qdrant_invoices/tools.tickets.yaml",
        "--env-file",
        "/path/to/repo/examples/qdrant_invoices/.env.example",
        "--name",
        "tickets"
      ],
      "cwd": "/path/to/repo/examples/qdrant_invoices"
    }
  }
}
```

Claude Desktop sandboxes the MCP **process**. Install the `vectorsmith` CLI somewhere Desktop can execute (for example a venv under `~/Claude` or `~/Documents`). A venv under `~/Downloads` will fail with `PermissionError` on `pyvenv.cfg` and the UI will show **Server disconnected**.

```bash
uv run vectorsmith serve examples/qdrant_invoices/tools.invoices.yaml --name invoices \
  --env-file examples/qdrant_invoices/.env.example
```

Ask Claude: “Which Globex invoices are overdue?” then “Which critical tickets are still open?”

Python apps import `load_tools` instead of spawning Desktop — [integrations](integrations/README.md). This page is only for Claude Desktop.

Claude-authored tools (optional):

```bash
uv run vectorsmith serve examples/qdrant_invoices/tools.invoices.yaml --name invoices \
  --env-file examples/qdrant_invoices/.env.example --enable-define
```

Then: “Make a tool that searches invoices by days overdue.” Review `tools.drafts.yaml` and run `vectorsmith approve NAME`.

`--watch` is on by default for **stdio** `serve` (not HTTP). Saving the project YAML **recompiles** that process (plans, schemas, hidden filters). Claude Desktop **does not** refresh the named connector tool list (it ignores `notifications/tools/list_changed`). At connect, Desktop sees your compiled tools **plus** two stable dispatchers: `list_available_tools` and `run_tool`. Those dispatchers re-validate arguments and still apply `static_filters`. Tools added to YAML after connect stay reachable through those two. The Connectors UI still looks stale until reconnect — that is Desktop, not VectorSmith. Pass `--no-meta-tools` if you prefer reconnect-only.
