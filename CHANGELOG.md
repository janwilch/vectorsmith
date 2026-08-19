# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

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
