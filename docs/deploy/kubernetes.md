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
| Readiness | `GET /readyz` (503 if a connection, required embedder, or JWT JWKS fetch is down) |

`--shutdown-grace-s` (default 30) matches `terminationGracePeriodSeconds`. During drain, new `POST /mcp` requests return 503; in-flight calls finish.

## Auth store

Two replicas sharing builtin OAuth need `--auth-store redis` and `--redis-url`. JWT mode is stateless (JWKS only).

## Secrets

Put the env file in a Secret (`envFileSecret`) and tools.yaml in a ConfigMap (`toolsYaml`). Do not bake URLs or keys into the image.

`connections.*.credentials.provider: k8s` reads an in-cluster Secret via the pod service account (`credentials.k8s.secret`). `vault` and `aws_sm` work the same as on a VM — [enterprise → credentials](../enterprise.md#credentials).

Local: `deploy-templates/compose/docker-compose.yaml` (Qdrant + Redis + serve).
