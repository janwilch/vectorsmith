# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [0.1.0] — 2026-08-19

First public release.

### Added

- `tools.yaml` (TDS v1): connections, user tools, opt-in built-ins, pipelines.
- Adapters: Qdrant, pgvector (vector + table), Chroma, Pinecone, Weaviate, Milvus.
- CLI: `init`, `validate`, `serve` (stdio + HTTP/OAuth), `test`, `introspect`, `drafts`, `approve`, `auth`.
- In-process API: `load_tools` (LangChain / LangGraph), `connect`, OpenAI Agents and Anthropic adapters.
- MCP host docs and examples: Claude Desktop, Claude Code, Codex, Cursor.
- Agent examples: LangChain, LangGraph, OpenAI Agents SDK, Anthropic Messages API.
