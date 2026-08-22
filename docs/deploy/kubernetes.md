# Kubernetes

Hub: [documentation home](../index.md). Chart: `deploy-templates/helm/vectorsmith/`.

```bash
helm install vectorsmith deploy-templates/helm/vectorsmith \
  --set replicaCount=2 \
  --set auth.mode=jwt \
  --set auth.jwksUrl=https://auth.example.com/.well-known/jwks.json \
  --set redis.enabled=true
```

## Probes

| Probe | Path |
|---|---|
| Liveness | `GET /healthz` |
| Readiness | `GET /readyz` (503 if a connection or required embedder is down) |

`--shutdown-grace-s` (default 30) matches `terminationGracePeriodSeconds`. During drain, new `POST /mcp` requests return 503; in-flight calls finish.

## Auth store

Two replicas sharing builtin OAuth need `--auth-store redis` and `--redis-url`. JWT mode is stateless (JWKS only).

## Secrets

Put the env file in a Secret (`envFileSecret`) and tools.yaml in a ConfigMap (`toolsYaml`). Do not bake URLs or keys into the image.

Local: `deploy-templates/compose/docker-compose.yaml` (Qdrant + Redis + serve).
