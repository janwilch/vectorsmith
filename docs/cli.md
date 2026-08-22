# CLI reference

Hub: [documentation home](index.md). Inventory of extras / routes: [library surface](library.md). Python env rules differ: [python-api.md](python-api.md).

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
vectorsmith validate TOOLS.yaml [--live] [--live-embed] [--json] [--strict] [--env-file FILE]
vectorsmith validate TOOLS.yaml --enterprise --strict
vectorsmith validate TOOLS.yaml --policy-builtin enterprise,pci,soc2
```

Compile, interpolate, synthesize built-ins, collect `VBxxxx` / `VE00x` / policy issues. No MCP server.

| Flag | Meaning |
|---|---|
| `--live` | Ping the store (health, embedding dim vs collection, sparse / hybrid, payload-path drift) |
| `--live-embed` | Also smoke-test the embedding provider (implies `--live`) |
| `--json` | Issues as JSON on stdout |
| `--strict` | Warnings → exit `1` |
| `--env-file` | Keys used for `${VAR}` under `connections` and embedding `config` |
| `--enterprise` / `--profile enterprise` | Production-safe preset (`VE001`–`VE007`) |
| `--policy FILE.rego` | Custom OPA policy (`POL000` if `opa` is missing) |
| `--policy-builtin` | Comma list: `enterprise`, `pci`, `soc2` |

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
vectorsmith serve projects/internal.yaml projects/external.yaml \
  --route-by-claim product --default-project internal --http 0.0.0.0:8080 --auth jwt
```

### Stdio (Claude Desktop, Claude Code, Codex, Cursor)

Default when `--http` is omitted. The host **spawns** this process.

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `VectorSmith` | MCP `serverInfo.name` — match the `mcpServers` / `mcp_servers` key |
| `--env-file` | | Interpolation map |
| `--watch` / `--no-watch` | `--watch` | Reload YAML (and `tools.drafts.yaml`) on save. Recompiles plans; Desktop still freezes the named list |
| `--enable-define` | off | Advertise `describe_collection` / `define_tool` (or set `authoring.define_tool: true` in YAML) |
| `--meta-tools` / `--no-meta-tools` | `--meta-tools` | Advertise `list_available_tools` / `run_tool`. Off = compiled tools only |

Default: compiled tools **plus** `list_available_tools` and `run_tool`. Those two exist because Claude Desktop freezes `tools/list` at connect. `run_tool` is **not** a schema bypass — inner args go through the named tool’s jsonschema and `static_filters` / request tenancy still AND. They are not advertised by `load_tools`. Use `--no-meta-tools` to hide them.

`--watch` reloads and recompiles; it does not make Desktop refresh the Connectors UI. Details: [FAQ](faq.md).

Drafts are written to **`./tools.drafts.yaml` (process cwd)**. Set `cwd` in the host config.

### HTTP (claude.ai, remote MCP)

```bash
vectorsmith serve tools.yaml --http 127.0.0.1:8080 --auth none --name invoices
vectorsmith serve tools.yaml --http 0.0.0.0:8080 --auth builtin --public-url https://example.com
vectorsmith serve tools.yaml --http 0.0.0.0:8080 --auth jwt \
  --jwt-issuer https://auth.example.com --jwt-audience vectorsmith \
  --jwks-url https://auth.example.com/.well-known/jwks.json
```

| Flag | Default | Meaning |
|---|---|---|
| `--http HOST:PORT` | | Streamable HTTP. MCP is `POST /mcp` |
| `--auth` | `builtin` | `none` (loopback only), `builtin`, `jwt`, or `api_key` |
| `--public-url` | required for `builtin` | Must be `https://…` |
| `--jwt-issuer` / `--jwt-audience` / `--jwks-url` | | JWT mode (or `security.auth.jwt` in YAML). Extra: `vectorsmith[auth-jwt]` |
| `--api-keys-file` | | JSON `{ "key": { "principal", "claims" } }` for `--auth api_key` |
| `--auth-store` / `--redis-url` | `sqlite` | Builtin OAuth token store. `redis` needs `vectorsmith[auth-redis]` |
| `--audit-log` / `--audit-sink` / `--audit-url` | | JSONL audit events (file is mode 0600) |
| `--route-by-claim` / `--default-project` | | Multi-YAML routing (HTTP). Tool names must be unique across files |
| `--shutdown-grace-s` | `30` | Drain in-flight MCP calls on SIGTERM; new `/mcp` POSTs get 503 |
| `--log-format` / `--log-level` | `text` / `info` | `json` adds `request_id` / `principal` / `tool` / `latency_ms` |

`--watch` is **ignored** on HTTP. Restart after YAML edits. `--meta-tools` / `--no-meta-tools` and `--enable-define` apply the same as stdio.

`GET /healthz` → `{"ok": true}`. `GET /readyz` → 503 if any connection (or embed, when required) is down. `GET /metrics` when `observability.metrics.enabled`. `builtin` OAuth: PKCE, DCR, tokens in `~/.vectorsmith/authstate.db` (mode 0600). First start writes the access secret once to `~/.vectorsmith/access-secret.once` (mode 0600) — it is not printed.

Exit: `2` if `builtin` lacks `https` `--public-url`, or jwt/api_key is missing JWKS/keys · `3` if `--auth none` is not loopback.

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

## `migrate`

```bash
vectorsmith migrate TOOLS.yaml --from 1 --to 2 --dry-run
vectorsmith migrate TOOLS.yaml --from 1 --to 2 --write
```

`--dry-run` prints a unified diff and does not write. `--write` rewrites the file (`tds_version: "2"`, list `static_filters` → `{must: …}`).

---

## `auth`

```bash
vectorsmith auth rotate-secret
vectorsmith auth revoke
```

Builtin HTTP OAuth admin. `rotate-secret` writes a new secret once to `~/.vectorsmith/access-secret.once` (mode 0600). `revoke` drops stored tokens.

---

## Exit codes (summary)

| Code | Typical |
|---|---|
| `0` | Success |
| `1` | `validate --strict` with warnings only |
| `2` | Validation / usage / missing draft / `builtin` missing `https` URL |
| `3` | Live `test` / `introspect` failure; `--auth none` off localhost |
