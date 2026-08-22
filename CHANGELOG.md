# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.3] — 2026-08-22

### Added

- Pluggable embedding providers: `fastembed` (default), `openai`, `azure_openai`, `http`, `cohere`. String `defaults.embedding` still works.
- `${VAR}` interpolation and secret lint under `defaults.embedding.config` / `query.embedding.config`.
- Extras `vectorsmith[embed-openai]` and `vectorsmith[embed-cohere]`. **VB2019** if the extra is missing.
- `validate --live-embed` smoke-tests the embedder. HTTP `GET /readyz` checks provider health when `serve --http --live-embed`.
- `static_filters` object form: `must` / `must_not` (bare list still means `must` only).
- `query.min_score` and `query.ef` (Qdrant `score_threshold` / HNSW `ef`; post-filter as a safety net).
- Request-scoped tenancy: `security.tenancy` (`claim` / `header`) ANDs a payload filter from caller identity. **VB4010** / **VB4011** / **VB4012**.
- HTTP auth providers: `--auth jwt` (JWKS / RS256) and `--auth api_key`, plus `--auth-store redis` for shared builtin OAuth tokens. Extras `vectorsmith[auth-jwt]` and `vectorsmith[auth-redis]`. `--auth none` is still loopback-only (exit 3).
- Tool-level RBAC: `security.rbac` (`roles`, `deny_tools`). Applied on `run_tool`. **VB4013** / **VB4014**.
- Audit log: `observability.audit` and `--audit-log` / `--audit-sink`. JSONL events; redacted args; sink failures do not block the call.
- Rate limits: `security.rate_limit` (off by default). Per-principal / per-tool / embed windows; Redis-shareable. HTTP **429** with `retry_after_s`.
- Parameter `resolve.kind: directory` (fuzzy / cached). **VB4020** / **VB4021**.
- `output.redact` (`omit` / `hash` / `mask` / `pattern`) and `output.max_field_length`. Applied before the result (and audit) is returned.
- Credential backends: `connections.*.credentials.provider` (`env` / `vault` / `aws_sm` / `k8s`). Missing secret still surfaces as `MissingEnvError`.
- `GET /readyz` checks every connection and embed health when search tools exist (or `--live-embed`). **503** if any fail. `GET /healthz` stays 200.
- Optional OpenTelemetry spans and Prometheus `GET /metrics`. Extra `vectorsmith[otel]`. Off by default.
- `validate --enterprise` / `--profile enterprise` (`VE001`–`VE007`) and `--policy` / `--policy-builtin` (`pci`, `soc2`, `enterprise`).
- Multi-project `serve`: extra YAML args, `--route-by-claim`, `--default-project`. Duplicate tool names fail at startup.
- Optional `query.expand` (N+1 embeds, merge by best score; failure **VB4030**) and `tool.rerank` (`retrieve_k` then reorder; failure **VB4031`). Both off by default.
- Helm chart, Docker image, and compose stack under `deploy-templates/` (readyz probes, Redis auth store, graceful drain).
- `vectorsmith migrate --from 1 --to 2` (`--dry-run` / `--write`). `tds_version: "2"` + `meta`. v1 still loads with **VB0002**.
- Request `deadline_s` → `QueryTimeout`. `--shutdown-grace-s` drains HTTP; new `POST /mcp` is **503** while draining.
- `--log-format json --log-level info`. Default text logs unchanged. JSON includes `request_id` (same as audit).
- Docs inventory page (`docs/library.md`): extras, HTTP routes, exceptions, public imports. YAML reference covers credentials, expand, resolve, redact, profiles, and remaining `VBxxxx` codes.

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
