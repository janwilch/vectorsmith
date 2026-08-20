# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.1.2] — 2026-08-20

### Added

- `vectorsmith serve --no-meta-tools` omits `list_available_tools` / `run_tool` (compiled tools only). Default remains on for Claude Desktop’s frozen `tools/list`.
- `validate --live` embedding fingerprint: **VB2017** (collection dim ≠ known embedder, error), **VB2018** (unknown model id, warning).
- `validate --live` payload-path drift: **VB4004** (YAML path not seen on sampled/native fields, warning).
- Qdrant search can request a payload include-list when the tool has `output.fields`; Milvus `search` uses `output_fields` the same way.

### Changed

- Compiler honors `defaults.embedding` on the execution plan. Per-tool `query.embedding` still wins.
- `run_tool` description states that inner arguments are re-validated against the named tool’s compiled schema and that `static_filters` still apply. `additionalProperties` on the MCP envelope is not a typing bypass.

### Fixed

- Documented Pinecone `collection` = index namespace and Weaviate connection `tenant` vs payload `static_filters`, so those are not mistaken for the same isolation layer.

## [0.1.1] — 2026-08-19

### Changed

- PyPI long description is the package README (install, two doors, YAML sketch, store extras).
- Builtin HTTP OAuth writes the one-time access secret to `~/.vectorsmith/access-secret.once` (mode 0600) instead of printing it.

### Fixed

- Secret-lint corpus no longer uses a Stripe `whsec_` sample that GitHub secret scanning treated as a live key.

## [0.1.0] — 2026-08-19

First public release.

### Added

- `tools.yaml` (TDS v1): connections, user tools, opt-in built-ins, pipelines.
- Adapters: Qdrant, pgvector (vector + table), Chroma, Pinecone, Weaviate, Milvus.
- CLI: `init`, `validate`, `serve` (stdio + HTTP/OAuth), `test`, `introspect`, `drafts`, `approve`, `auth`.
- In-process API: `load_tools` (LangChain / LangGraph), `connect`, OpenAI Agents and Anthropic adapters.
- MCP host docs and examples: Claude Desktop, Claude Code, Codex, Cursor.
- Agent examples: LangChain, LangGraph, OpenAI Agents SDK, Anthropic Messages API.
