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

## Supported versions

The latest `0.1.x` release on the default branch is what we patch.
