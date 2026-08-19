# Repository map

This is what GitHub visitors see and where the rest lives.

| Path | What it is |
|---|---|
| [README.md](../README.md) | Landing page: why VectorSmith exists, YAML sketch, two consumption paths |
| [docs/](README.md) | Full manual (this tree) |
| [examples/](../examples/README.md) | Invoice + ticket YAML, four agent apps, MCP host configs |
| [packages/core](../packages/core) | `vectorsmith-core` — schema, compiler, store adapters |
| [packages/cli](../packages/cli) | Published `vectorsmith` — CLI + `load_tools` / `connect` |
| [deploy-templates/](../deploy-templates/README.md) | Docker / Kubernetes / Cloud Run / Fly for HTTP MCP |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, PR rules, versioning |
| [SUPPORT.md](../SUPPORT.md) | Where to ask for help |
| [SECURITY.md](../SECURITY.md) | Vulnerability reports (private) |
| [CHANGELOG.md](../CHANGELOG.md) | User-visible changes |
| [LICENSE](../LICENSE) · [NOTICE](../NOTICE) | Apache-2.0 |

Do not import `Engine`. Application code uses `from vectorsmith import load_tools` or `connect`, or the `vectorsmith` CLI.
