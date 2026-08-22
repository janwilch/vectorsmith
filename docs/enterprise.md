# Enterprise security model

Hub: [documentation home](index.md). Hardening checklist: [security-hardening.md](security-hardening.md).

VectorSmith is a **compiler**, not an identity provider or access plane. You own auth, host choice, and the store. This page is the security model the compiler and `serve` enforce when you turn the knobs on.

## Layers

| Layer | Where | What it does |
|---|---|---|
| Hidden filters | `static_filters` | Always AND. The model never sees them |
| Request tenancy | `security.tenancy` | Extra payload filter from JWT claim or header |
| Auth | `--auth jwt` / `api_key` / `builtin` | Who is calling HTTP `/mcp` |
| RBAC | `security.rbac` | Which compiled tools that principal may invoke |
| Audit | `observability.audit` | One event per named tool call |
| Rate limits | `security.rate_limit` | Off by default; HTTP **429** |
| Output policy | `output.redact` | Applied before the result (and audit) leaves the process |

`--auth none` is loopback only (exit 3 off localhost). Builtin OAuth still requires `https://` `--public-url`.

## Tenancy

`security.tenancy.mode`:

- `none` — no request filter (YAML `static_filters` still apply)
- `static` — this process is one tenant; use `static_filters`
- `claim` — value from JWT (`claim: tenant_id`)
- `header` — value from an HTTP header

The engine ANDs `tenant_filter` with `must` / `must_not`. `enforce: strict` rejects a model argument that conflicts (**VB4010**).

## Auth and RBAC

HTTP `--auth jwt` validates RS256 via JWKS (`vectorsmith[auth-jwt]`). `--auth api_key` reads a keys file. `--auth-store redis` shares builtin OAuth tokens across replicas.

`security.rbac.deny_tools` wins over `allow: ["*"]`. Checks apply to the **inner** name of `run_tool`.

## Audit

JSONL: `request_id`, `principal`, tool, connection, redacted args, result count, latency. Sink failures do not block the call. Default redact: `password`, `token`, `secret`.

## Credentials

`connections.*.credentials.provider` defaults to `env`. `vault` is implemented as `VaultCredentialResolver` (inject a `fetch` callable; TTL cache). `serve` still uses the env resolver. `aws_sm` / `k8s` are reserved on the model. Details: [tools.yaml → credentials](tools-yaml-reference.md#credentials).

## Reference YAML

See [`examples/enterprise/`](https://github.com/kjgpta/vectorsmith/tree/main/examples/enterprise). Full inventory: [library surface](library.md).
