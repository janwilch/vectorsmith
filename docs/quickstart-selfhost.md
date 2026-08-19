# Self-host (claude.ai custom connector)

Hub: [documentation home](README.md) · [CLI](cli.md) · [Deploy](../deploy-templates/README.md).

Streamable HTTP MCP. Endpoint is **`POST /mcp`**. `GET /healthz` returns `{"ok": true}`. Any MCP client can attach the same way.

`--watch` does **not** apply to HTTP (`serve --http` never reloads YAML). Restart the process after edits.

Default `--auth` is `builtin`. Localhost demos must pass `--auth none` explicitly:

```bash
uv run vectorsmith serve examples/qdrant_invoices/tools.invoices.yaml --name invoices \
  --http 127.0.0.1:8080 --auth none
```

`--auth none` is refused off loopback (exit **3**): not `0.0.0.0`, not a public hostname.

For a public URL, `builtin` requires `https://` `--public-url` (exit **2** if missing):

```bash
uv run vectorsmith serve examples/qdrant_invoices/tools.invoices.yaml --name invoices \
  --http 0.0.0.0:8080 --auth builtin --public-url https://vb.example.com
```

The process prints an access secret once. Builtin OAuth is PKCE S256, DCR, opaque tokens in `~/.vectorsmith/authstate.db` (mode 0600).

```bash
uv run vectorsmith auth rotate-secret
uv run vectorsmith auth revoke
```

Unauthenticated `POST /mcp` returns **401** with:

`WWW-Authenticate: Bearer resource_metadata="<public-url>/.well-known/oauth-protected-resource"`

Also served: `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`, `/oauth/authorize`, `/oauth/token`, `/oauth/register`, `/oauth/revoke`.

Add the connector in claude.ai (URL `https://vb.example.com/mcp`). Add Slack/GitHub/etc. as **separate** connectors — see [coexistence.md](coexistence.md).

Container / k8s / Cloud Run / Fly: [deploy-templates/](../deploy-templates/README.md).
