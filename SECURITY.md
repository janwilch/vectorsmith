# Security

## Report a vulnerability

Use **GitHub Security Advisories** on this repository (Security → Advisories → New draft).

Do **not** open a public issue for a vulnerability, leaked credential, or auth bypass.

We aim to acknowledge reports within 7 days.

## What this software does with secrets

- `tools.yaml` must reference credentials as `${VAR}` under `connections` only. Inline keys fail load.
- `vectorsmith serve --http --auth builtin` requires `https://` `--public-url`. `--auth none` is localhost-only.
- `--env-file` for the CLI (`validate` / `serve` / `test` interpolate **only** keys from that file).
- `load_tools` / `connect` merge `os.environ`, then `env=`, then `env_file=`.

## `run_tool` (MCP serve)

`list_available_tools` and `run_tool` are advertised by `vectorsmith serve` so Claude Desktop can reach tools added after connect (Desktop freezes the named list). They are not part of `load_tools` / `connect`.

`run_tool` is a dispatcher, not a second permission model:

- Inner `arguments` are validated against the **named** tool’s compiled JSON Schema (types, enums, required, limits).
- Hidden `static_filters` on that tool still AND into the store query. Omitting `tenant` from arguments does not drop the compiled tenant condition.
- `run_tool` cannot call itself. Unknown names fail like any other missing tool.

Serve with `--no-meta-tools` to omit both dispatchers. That does not loosen named-tool validation.

## Supported versions

The latest `0.1.x` release on the default branch is what we patch.
