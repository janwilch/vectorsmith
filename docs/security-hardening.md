# Production hardening

Hub: [documentation home](index.md). Security model: [enterprise.md](enterprise.md).

```bash
vectorsmith validate tools.yaml --enterprise --strict --env-file .env
vectorsmith validate tools.yaml --policy-builtin enterprise,pci,soc2
```

## `--enterprise` rules

| Code | Rule |
|---|---|
| VE001 | `authoring.define_tool: true` is an error |
| VE002 | `tenancy.mode: none` and no `must` filter on a tool |
| VE003 | `output.limit_max` > 100 |
| VE004 | Connection `url` / `dsn` / `host` is not `${VAR}` (checked on raw YAML) |
| VE005 | Meta tools still advertised (warning; use `--no-meta-tools`) |
| VE006 | Builtin auth on a public URL without HTTPS (serve-time) |
| VE007 | `defaults.embedding.provider: fastembed` (warning) |

`--profile enterprise` merges `profiles.enterprise.security.hardening` from the YAML.

## Checklist

1. Secrets only via `${VAR}` under allowed interpolation paths
2. `--auth jwt` or `api_key` in front of HTTP; never `--auth none` on a public bind
3. `security.tenancy.mode: claim` (or header) plus YAML `must` filters
4. `security.rbac.enabled` with explicit roles; `deny_tools` for authoring
5. `observability.audit.enabled` to a file (0600) or HTTP sink
6. `serve --no-meta-tools` unless a Desktop host needs the freeze workaround
7. `output.limit_max` ≤ 100; `output.redact` for PAN / tokens
8. Two replicas + Redis auth store ([Kubernetes](deploy/kubernetes.md))
9. `--shutdown-grace-s 30` and `--log-format json`
10. CI: `validate --enterprise --strict`

Policy packs (`pci`, `soc2`) ship in `vectorsmith_core/policy/`. Custom Rego needs the `opa` CLI (`POL000` if missing).
