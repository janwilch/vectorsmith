# Deploy templates

Hub: [documentation home](../docs/README.md) · [HTTP quickstart](../docs/quickstart-selfhost.md).

HTTP MCP (`vectorsmith serve --http`) for claude.ai or any remote MCP client. Stdio hosts (Desktop, Codex, Cursor) do not need these — they spawn the CLI locally.

`--watch` is stdio-only; a containerized HTTP server does not reload YAML until you restart the process.

`--auth none` is localhost-only. Public bind requires `--auth jwt`, `api_key`, or `--auth builtin --public-url https://…`. The MCP route is `/mcp`. Liveness is `GET /healthz`. Readiness is `GET /readyz` (503 if a connection, required embedder, or JWT JWKS is down).

| File | Use |
|---|---|
| [Dockerfile](Dockerfile) | Image; build from the **repository root** |
| [docker/Dockerfile](docker/Dockerfile) | Same image, JWT/Redis extras, `--shutdown-grace-s` |
| [compose/docker-compose.yaml](compose/docker-compose.yaml) | Qdrant + Redis + serve for local HTTP |
| [helm/vectorsmith](helm/vectorsmith) | Chart: probes, HPA, PDB, Redis auth store, ingress |
| [k8s.yaml](k8s.yaml) | Deployment + Service |
| [cloudrun.yaml](cloudrun.yaml) | Cloud Run |
| [fly.toml](fly.toml) | Fly.io |

Set `QDRANT_URL` (or other store vars from your `tools.yaml`) and `PUBLIC_URL` at runtime. Do not bake API keys into the image.
