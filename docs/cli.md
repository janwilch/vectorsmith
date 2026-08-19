# CLI reference

Hub: [documentation home](index.md). Python env rules differ: [python-api.md](python-api.md).

```bash
vectorsmith --help
vectorsmith COMMAND --help
```

All commands that read YAML take a path to a TDS file. Secrets: **`--env-file` only** — the process environment is not merged. Use `${VAR:-default}` in YAML if you have no file. Python APIs merge `os.environ`; see [python-api.md](python-api.md).

Default MCP instance name is `VectorSmith` (`--name`). Product title is always `VectorSmith`.

---

## `init`

```bash
vectorsmith init [DIRECTORY]
vectorsmith init ./demo --print-desktop-config --name invoices
```

Writes `tools.yaml` and `.env.example` if they do not exist. `--print-desktop-config` prints a Claude Desktop JSON block (includes a sample `filesystem` server) to stdout.

---

## `validate`

```bash
vectorsmith validate TOOLS.yaml [--live] [--json] [--strict] [--env-file FILE]
```

Compile, interpolate, synthesize built-ins, collect `VBxxxx` issues. No MCP server.

| Flag | Meaning |
|---|---|
| `--live` | Ping the store (health, dims, sparse / hybrid) |
| `--json` | Issues as JSON on stdout |
| `--strict` | Warnings → exit `1` |
| `--env-file` | Keys used for `${VAR}` under `connections` |

Exit: `0` ok · `1` warnings with `--strict` · `2` errors.

---

## `test`

```bash
vectorsmith test TOOLS.yaml TOOL_NAME [--args JSON] [--show-plan] [--env-file FILE]
```

Run one compiled tool. Authoring smoke-test — not the app API.

| Flag | Meaning |
|---|---|
| `--args` | JSON object (default `{}`) |
| `--show-plan` | Print MCP schema + plan kind/collection/mode on stderr; `debug` on the call |

Exit: `0` ok · `2` unknown tool / validation errors · `3` live call failed.

Stdout is the result envelope (truncated to 20k characters).

---

## `serve`

```bash
vectorsmith serve TOOLS.yaml [OPTIONS]
```

### Stdio (Claude Desktop, Claude Code, Codex, Cursor)

Default when `--http` is omitted. The host **spawns** this process.

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `VectorSmith` | MCP `serverInfo.name` — match the `mcpServers` / `mcp_servers` key |
| `--env-file` | | Interpolation map |
| `--watch` / `--no-watch` | `--watch` | Reload YAML (and `tools.drafts.yaml`) on save |
| `--enable-define` | off | Advertise `describe_collection` / `define_tool` (or set `authoring.define_tool: true` in YAML) |

Always advertised: compiled tools **plus** `list_available_tools` and `run_tool` (Desktop freezes the named list at connect).

Drafts are written to **`./tools.drafts.yaml` (process cwd)**. Set `cwd` in the host config.

### HTTP (claude.ai, remote MCP)

```bash
vectorsmith serve tools.yaml --http 127.0.0.1:8080 --auth none --name invoices
vectorsmith serve tools.yaml --http 0.0.0.0:8080 --auth builtin --public-url https://example.com
```

| Flag | Default | Meaning |
|---|---|---|
| `--http HOST:PORT` | | Streamable HTTP. MCP is `POST /mcp` |
| `--auth` | `builtin` | `none` (loopback only) or `builtin` |
| `--public-url` | required for `builtin` | Must be `https://…` |

`--watch` is **ignored** on HTTP. Restart after YAML edits.

`GET /healthz` → `{"ok": true}`. `builtin` OAuth: PKCE, DCR, tokens in `~/.vectorsmith/authstate.db` (mode 0600). First start prints an access secret once.

Exit: `2` if `builtin` lacks `https` `--public-url` · `3` if `--auth none` is not loopback.

Details: [HTTP quickstart](quickstart-selfhost.md).

---

## `introspect`

```bash
vectorsmith introspect TOOLS.yaml --connection NAME [--out schema.json] \
  [--collections a,b] [--redact-examples] [--audit] [--env-file FILE]
```

Metadata-only export (field names / types — not a row dump). `--audit` prints JSON instead of writing `--out`. `--connection` is required.

Exit `3` on live failure.

---

## `drafts` / `approve`

```bash
vectorsmith drafts list
vectorsmith drafts reject NAME
vectorsmith approve NAME [--file tools.yaml]
```

Reads `./tools.drafts.yaml` in the current working directory. Cap **10** pending; pending drafts **30 days** old expire on serve.

`approve` interpolates the target YAML with an **empty** env map. Use `${VAR:-default}` in that file or interpolation fails. `--file` defaults to `tools.yaml`.

---

## `auth`

```bash
vectorsmith auth rotate-secret
vectorsmith auth revoke
```

Builtin HTTP OAuth admin. `rotate-secret` prints a new secret once. `revoke` drops stored tokens.

---

## Exit codes (summary)

| Code | Typical |
|---|---|
| `0` | Success |
| `1` | `validate --strict` with warnings only |
| `2` | Validation / usage / missing draft / `builtin` missing `https` URL |
| `3` | Live `test` / `introspect` failure; `--auth none` off localhost |
