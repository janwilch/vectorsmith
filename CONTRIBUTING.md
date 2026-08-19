# Contributing

User-facing documentation lives in [`docs/`](docs/index.md) and is published at [kjgpta.github.io/vectorsmith](https://kjgpta.github.io/vectorsmith/). If you change YAML fields, CLI flags, or an integration path, update the matching page there (and the FAQ if the failure mode is new). Preview with `mkdocs serve` after `pip install 'mkdocs>=1.6,<2' mkdocs-material mkdocs-autorefs`.

## Setup

Python 3.11+. [uv](https://docs.astral.sh/uv/) is required.

```bash
uv sync
uv run ruff check .
uv run pytest -m "not conformance"
uv run lint-imports
```

`uv run mypy` covers `vectorsmith_core`. Adapter conformance tests (`pytest -m conformance`) need `docker compose up -d` and are not required for typical PRs.

## Layout

| Path | Role |
|---|---|
| `packages/core` | `vectorsmith-core` — TDS, compiler, adapters |
| `packages/cli` | `vectorsmith` — CLI + `load_tools` / `connect` |
| `docs/` | User documentation |
| `examples/` | Runnable samples |
| `tests/unit` | Fast tests (CI) |

`vectorsmith_core` must not import `vectorsmith` or `vectorsmith_cli` (enforced by import-linter).

## Pull requests

- Keep changes focused. Do not mix refactors with feature work.
- Add or update a unit test when you change compiler, loader, or public API behavior.
- Update `docs/` if you change `tools.yaml` fields, CLI flags, or an integration path.
- Do not commit `.env`, credentials, or `tools.drafts.yaml`.
- Do not commit files under `.internal/` (unpublished notes).

## Versioning

Package versions live in:

- `packages/core/pyproject.toml`
- `packages/cli/pyproject.toml`
- `packages/core/vectorsmith_core/version.py` (`ENGINE_VERSION`, shown by `serve`)

Keep those three in sync. After a user-visible change, add a note to `CHANGELOG.md`.

## Publishing (maintainers)

Source: [github.com/kjgpta/vectorsmith](https://github.com/kjgpta/vectorsmith).

1. Add PyPI [trusted publishing](https://docs.pypi.org/trusted-publishers/) for both `vectorsmith` and `vectorsmith-core`, pointed at `.github/workflows/release.yml`.
2. Run the **Release** workflow (`dry_run` first, then publish), or tag `v0.1.0`.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
