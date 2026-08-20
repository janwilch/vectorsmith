# Claude Desktop

Hub: [documentation home](../index.md) · [Integrations](README.md).

Claude Desktop is an MCP host. It cannot `import vectorsmith`. It **spawns** `vectorsmith serve` and lists the tools under **Connectors**.

Worked Desktop walkthrough (paths, sandbox, `--watch`): [Desktop quickstart](../quickstart-desktop.md).

## Config

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Linux: `~/.config/Claude/claude_desktop_config.json`

Each `mcpServers` key is the connector name Claude shows. Pass the same string to `--name`.

```json
{
  "mcpServers": {
    "invoices": {
      "command": "vectorsmith",
      "args": [
        "serve",
        "/absolute/path/tools.invoices.yaml",
        "--env-file",
        "/absolute/path/.env",
        "--name",
        "invoices"
      ],
      "cwd": "/absolute/path"
    },
    "tickets": {
      "command": "vectorsmith",
      "args": [
        "serve",
        "/absolute/path/tools.tickets.yaml",
        "--env-file",
        "/absolute/path/.env",
        "--name",
        "tickets"
      ],
      "cwd": "/absolute/path"
    }
  }
}
```

`command` must be an executable Desktop can run. A venv under `~/Downloads` is often sandboxed (`PermissionError` on `pyvenv.cfg` → **Server disconnected**). Install into `~/Claude` or `~/Documents`, or use an absolute path to that venv's `vectorsmith`.

Print a starter block:

```bash
vectorsmith init ./demo --print-desktop-config --name invoices
```

## After restart

Ask: “Which Globex invoices are overdue?”

Desktop freezes the named tool list at connect. At connect you get your compiled tools **plus** `list_available_tools` and `run_tool` (same jsonschema + `static_filters` as calling the tool by name). After a YAML reload (stdio `--watch`), new tools are reachable through those two without reconnecting. Omit them with `--no-meta-tools`. Details: [Desktop quickstart](../quickstart-desktop.md) · [FAQ](../faq.md).

Set `cwd` to the project directory so `tools.drafts.yaml` (authoring) is written next to the YAML.

## Next to Slack / GitHub / filesystem

Add more keys under `mcpServers`. See [coexistence](../coexistence.md).
