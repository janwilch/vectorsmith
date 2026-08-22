# Security

## Report a vulnerability

Use **GitHub Security Advisories** on this repository (Security → Advisories → New draft).

Do **not** open a public issue for a vulnerability, leaked credential, or auth bypass.

We aim to acknowledge reports within 7 days.

## What this software does with secrets

- `tools.yaml` must reference credentials as `${VAR}` under `connections` only. Inline keys fail load.
- `vectorsmith serve --http --auth builtin` requires `https://` `--public-url`. `--auth none` is localhost-only.
- `--auth jwt` validates Bearer JWTs against a JWKS (`--jwks-url`). Expired or invalid tokens are `401` / `auth_error` and never reach a tool.
- `--auth api_key` looks up keys in a JSON file (`principal` + optional `claims` for tenancy).
- `security.rbac` (off by default) allow-lists tools by JWT `roles` claim. `deny_tools` always wins, including through `run_tool`.
- Audit events never include row payloads or connection credentials. Named arg fields (default `password`, `token`, `secret`) are replaced with `[REDACTED]`.
- `--env-file` for the CLI (`validate` / `serve` / `test` interpolate **only** keys from that file).
- `load_tools` / `connect` merge `os.environ`, then `env=`, then `env_file=`.

## `run_tool` (MCP serve)

`list_available_tools` and `run_tool` are advertised by `vectorsmith serve` so Claude Desktop can reach tools added after connect (Desktop freezes the named list). They are not part of `load_tools` / `connect`.

`run_tool` is a dispatcher, not a second permission model:

- Inner `arguments` are validated against the **named** tool’s compiled JSON Schema (types, enums, required, limits).
- Hidden `static_filters` on that tool still AND into the store query. Omitting `tenant` from arguments does not drop the compiled tenant condition.
- Request-scoped `security.tenancy` (claim or header) is applied on the same path. The model cannot omit it; a conflicting argument is **VB4010** when `enforce: strict`.
- `run_tool` cannot call itself. Unknown names fail like any other missing tool.

Serve with `--no-meta-tools` to omit both dispatchers. That does not loosen named-tool validation.

## Supported versions

The latest `0.1.x` release on the default branch is what we patch.
