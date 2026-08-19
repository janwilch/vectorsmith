# Deploy templates

Hub: [documentation home](../docs/README.md) · [HTTP quickstart](../docs/quickstart-selfhost.md).

HTTP MCP (`vectorsmith serve --http`) for claude.ai or any remote MCP client. Stdio hosts (Desktop, Codex, Cursor) do not need these — they spawn the CLI locally.

`--watch` is stdio-only; a containerized HTTP server does not reload YAML until you restart the process.

`--auth none` is localhost-only. Public bind requires `--auth builtin --public-url https://…`. The MCP route is `/mcp`; liveness is `GET /healthz`.

| File | Use |
|---|---|
| [Dockerfile](Dockerfile) | Image; build from the **repository root** |
| [k8s.yaml](k8s.yaml) | Deployment + Service |
| [cloudrun.yaml](cloudrun.yaml) | Cloud Run |
| [fly.toml](fly.toml) | Fly.io |

Set `QDRANT_URL` (or other store vars from your `tools.yaml`) and `PUBLIC_URL` at runtime. Do not bake API keys into the image.
