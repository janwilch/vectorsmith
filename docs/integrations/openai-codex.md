# OpenAI Codex (CLI, IDE, ChatGPT desktop)

Hub: [documentation home](../README.md) · [Integrations](README.md).

Codex is an MCP host. The ChatGPT desktop app, Codex CLI, and IDE extension share one config. Codex does **not** use Claude’s JSON file.

Official reference: [developers.openai.com/codex/mcp](https://developers.openai.com/codex/mcp).

This is **not** the [OpenAI Agents SDK](openai-agents.md). Codex = host that **spawns** `serve`. Agents SDK = your Python process calls `load_tools`.

## Config

- User-wide: `~/.codex/config.toml`
- Project (trusted dirs only): `.codex/config.toml`

The table name is `mcp_servers` (underscores). `mcp-servers` or `mcpServers` is ignored.

```toml
[mcp_servers.invoices]
command = "vectorsmith"
args = [
  "serve",
  "/absolute/path/tools.invoices.yaml",
  "--env-file",
  "/absolute/path/.env",
  "--name",
  "invoices",
]
cwd = "/absolute/path"
startup_timeout_sec = 30
tool_timeout_sec = 60

[mcp_servers.tickets]
command = "vectorsmith"
args = [
  "serve",
  "/absolute/path/tools.tickets.yaml",
  "--env-file",
  "/absolute/path/.env",
  "--name",
  "tickets",
]
cwd = "/absolute/path"
startup_timeout_sec = 30
```

First start can download the embedding model. `startup_timeout_sec = 30` avoids a false “server failed to start”.

## CLI

```bash
codex mcp add invoices -- vectorsmith serve /absolute/path/tools.invoices.yaml \
  --env-file /absolute/path/.env --name invoices

codex mcp list
```

In a session, `/mcp` lists connected servers and tools.

## HTTP

```toml
[mcp_servers.invoices]
url = "http://127.0.0.1:8080/mcp"
```

Start the process with `vectorsmith serve tools.invoices.yaml --name invoices --http 127.0.0.1:8080 --auth none` (localhost only). HTTP serve does not reload YAML on save. Remote + OAuth: [self-host](../quickstart-selfhost.md) and Codex `codex mcp login`.
