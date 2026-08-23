# Embedding providers

Hub: [documentation home](index.md). Field reference: [tools.yaml](tools-yaml-reference.md).

`defaults.embedding` may be a string (`fastembed/BAAI/bge-small-en-v1.5`) or an object. Per-tool `query.embedding` wins. `${VAR}` is allowed only under `config`.

| Provider | Extra | Config |
|---|---|---|
| `fastembed` | store extra / `embed` | `model` |
| `openai` | `vectorsmith[embed-openai]` | `api_key`, `base_url`, `timeout_s`, `batch_size` |
| `azure_openai` | `vectorsmith[embed-openai]` | `api_key`, `endpoint`, `deployment`, `api_version` |
| `http` | (httpx, built-in) | `base_url`, `api_key`, `headers`, `request`, `response` |
| `cohere` | `vectorsmith[embed-cohere]` | `api_key`, `model` |

```yaml
defaults:
  embedding:
    provider: openai
    model: text-embedding-3-large
    dims: 3072
    config:
      api_key: ${OPENAI_API_KEY}
      timeout_s: 30
```

### HTTP gateway

```yaml
defaults:
  embedding:
    provider: http
    model: my-model
    dims: 1536
    config:
      base_url: ${EMBED_BASE_URL}
      api_key: ${EMBED_API_KEY:-}
      timeout_s: 120
      batch_size: 32
      request:
        model_field: model
        input_field: input
      response:
        vectors_path: data[*].embedding
```

Default JSON body is `{model, input: [texts]}`. Default vector path is OpenAI-shaped `data[*].embedding`. `dims` is required for unknown model ids (**VB2018** without it on `--live`).

**VB2019** if the provider extra is missing. `validate --live-embed` smoke-tests the embedder. HTTP `GET /readyz` checks provider health on **every** loaded project that has search/pipeline tools, or when you pass `--live-embed`.

### Query expansion

Separate from embeddings. `query.expand` (`openai` / `http` / `none`) rewrites the user string, then this embedder runs on each variant. Off by default. Failure → original query + **VB4030**. YAML: [tools.yaml → query.expand](tools-yaml-reference.md#queryexpand).
