# FAQ

Hub: [documentation home](README.md) · [Getting started](getting-started.md) · [CLI](cli.md).

## Install and run

### `vectorsmith: command not found`

Install so the CLI is on `PATH`: `pip install "vectorsmith[qdrant]"` (or `uv sync` in this repo, then `uv run vectorsmith …`). Claude Desktop often cannot see a venv under `~/Downloads` — [Desktop](quickstart-desktop.md).

### Validation says a variable is missing, but it is in my shell

The CLI interpolates **only** `--env-file`. Exporting `QDRANT_URL` in the terminal does nothing unless that key is in the file (or the YAML uses `${QDRANT_URL:-default}`).

`load_tools` / `connect` **do** read `os.environ`.

Host JSON `env: { "QDRANT_URL": "…" }` is **not** used for `${VAR}` in YAML. Keep using `--env-file`.

### Desktop shows **Server disconnected**

The MCP process cannot start. Common cause: sandboxed `~/Downloads` venv (`PermissionError` on `pyvenv.cfg`). Install under `~/Claude` or `~/Documents`, or set `command` to that venv’s absolute `vectorsmith` binary.

### Claude never sees a tool I just added to YAML

Desktop freezes the named list at connect. Stdio `--watch` reloads the server; call `list_available_tools` then `run_tool`. Or reconnect. HTTP `serve` does not watch — restart the process.

### `serve --http` exits 2 or 3

| Exit | Cause |
|---|---|
| `3` | `--auth none` on a non-loopback bind (`0.0.0.0`, a hostname) |
| `2` | `--auth builtin` (the default) without `https://` `--public-url` |

Local: `--http 127.0.0.1:8080 --auth none`. Public: `--auth builtin --public-url https://…`.

---

## YAML and tools

### Is this the same as official Qdrant / Pinecone MCP?

No. Vendor servers are cluster admin (often including writes). VectorSmith is **read-only**, tenant-scoped tools you declared. You can run both — [coexistence](coexistence.md).

### Why isn’t `tenant` in the tool schema?

`static_filters` are applied on every call and are not advertised. Put org isolation there so the model cannot skip it.

### `defaults.embedding` does not change the model

The field is valid TDS but the compiler does not read it yet. Set `query.embedding` on the search tool, or keep the default `fastembed/BAAI/bge-small-en-v1.5`. The collection dims must match.

### Hybrid search fails (`VB2012` / `VB2013`)

Needs a backend with hybrid (Qdrant, Weaviate, Milvus, Pinecone) **and** sparse vectors on the collection. Confirm with `validate --live`. Chroma and pgvector do not support hybrid.

### Name collision `VB2010` / `search_invoices`

Built-in `semantic_search` on connection `invoices` synthesizes `search_invoices`. Turn the built-in off or rename the connection. The invoice example omits built-ins for this reason.

### Two collections, one Claude connector or two?

One YAML with two `connections` = **one** `serve` = one connector. Two YAML files and two `serve --name` processes = two connectors (this repo: `invoices` and `tickets`).

---

## Python

### `from vectorsmith import load_tools` fails with missing `langchain_core`

Install `vectorsmith[langchain]` (or `[langgraph]`). For no LangChain: `from vectorsmith import connect`.

### Do I call `Engine`?

No. Use `connect` / `load_tools` or `vectorsmith serve`.

### Slack / GitHub next to VectorSmith in LangChain?

Keep them as MCP clients (`langchain-mcp-adapters`). VectorSmith tools stay in-process `load_tools` — [LangChain](integrations/langchain.md).

---

## Authoring

### Where is `tools.drafts.yaml`?

The process **cwd**. Set `cwd` in Desktop/Codex. Cap 10 pending; 30-day expiry.

### `approve` fails missing env

`approve` interpolates with an empty env map. Use `${VAR:-default}` in the YAML you approve into.

---

## Still stuck

Repro with `validate --json` and a redacted `tools.yaml`. Security issues: [SECURITY.md](../SECURITY.md), not a public GitHub issue.
