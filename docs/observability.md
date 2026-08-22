# Observability

Hub: [documentation home](index.md).

## Audit

`observability.audit` plus `--audit-log` / `--audit-sink` / `--audit-url`. JSONL events include `request_id` (same id as JSON logs and traces). Rows and credentials are never written. Default arg redact: `password`, `token`, `secret`.

## Tracing

Off by default. Extra: `vectorsmith[otel]`.

Spans:

- `vectorsmith.tool.call` — tool, principal, connection, collection
- `vectorsmith.embed` — provider, model, text_count
- `vectorsmith.adapter.search` — backend, collection, limit, mode
- `vectorsmith.pipeline.step` — step_kind

## Metrics

Off by default. When `observability.metrics.enabled`, HTTP serve exposes `GET /metrics`:

```
vectorsmith_tool_calls_total{tool,status}
vectorsmith_tool_latency_seconds{tool}
vectorsmith_embed_requests_total{provider}
vectorsmith_adapter_errors_total{backend,code}
vectorsmith_rate_limit_hits_total{tool}
```

HTTP: `GET /healthz` (liveness), `GET /readyz` (503 if a connection or required embedder is down), `GET /metrics` when metrics are enabled. Routes: [library surface](library.md#http-routes-serve---http).

## Logs

```bash
vectorsmith serve tools.yaml --http 127.0.0.1:8080 --auth none \
  --log-format json --log-level info
```

Default is text (dev). JSON fields: `level`, `ts`, `request_id`, `principal`, `tool`, `latency_ms`, `msg`. Credentials and embedding vectors are not logged.
