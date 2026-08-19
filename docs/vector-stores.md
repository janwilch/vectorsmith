# Vector stores

Hub: [documentation home](index.md) · [tools.yaml](tools-yaml-reference.md) · [Python API](python-api.md).

VectorSmith talks to **your** cluster. It does not host a database. These six backends ship in the package; pick the extra that matches `connections.*.backend` in `tools.yaml`.

## What is integrated

| Store | `backend` in YAML | Install extra | Client pulled in |
|---|---|---|---|
| [Qdrant](https://qdrant.tech/) | `qdrant` | `vectorsmith[qdrant]` | `qdrant-client` |
| [PostgreSQL + pgvector](https://github.com/pgvector/pgvector) | `pgvector` | `vectorsmith[pgvector]` | `psycopg` (binary + pool) |
| [Chroma](https://www.trychroma.com/) | `chroma` | `vectorsmith[chroma]` | `chromadb` |
| [Pinecone](https://www.pinecone.io/) | `pinecone` | `vectorsmith[pinecone]` | `pinecone` |
| [Weaviate](https://weaviate.io/) | `weaviate` | `vectorsmith[weaviate]` | `weaviate-client` |
| [Milvus](https://milvus.io/) | `milvus` | `vectorsmith[milvus]` | `pymilvus` |

Every store extra also installs **FastEmbed** (`BAAI/bge-small-en-v1.5` by default) so search can embed queries locally. You do not need a separate embed extra on the published `vectorsmith` package.

```bash
pip install "vectorsmith[qdrant]"     # most common
pip install "vectorsmith[pgvector]"
pip install "vectorsmith[chroma]"
pip install "vectorsmith[pinecone]"
pip install "vectorsmith[weaviate]"
pip install "vectorsmith[milvus]"
```

Install more than one extra if a single `tools.yaml` has mixed `backend`s. The CLI (`serve`, `validate`, `test`) and `connect()` / `load_tools` use the same extras.

There is **no** first-party adapter for other stores (Elasticsearch, Redis, OpenSearch, …). Those are not integrated.

## What each backend can do

Same tools (`search`, `lookup`, `count`, `scroll`, `pipeline`) compile against every backend. Capability gates reject YAML that the store cannot run (`validate`, including `validate --live` for hybrid/sparse).

| | Qdrant | pgvector | Chroma | Pinecone | Weaviate | Milvus |
|---|---|---|---|---|---|---|
| Dense search | yes | yes (vector mode) | yes | yes | yes | yes |
| Hybrid / sparse | yes | no | no | yes | yes | yes |
| Nested payload paths | yes | yes | no | no | yes | yes |
| `exists` / `is_null` | yes | yes | no | no | yes | `exists` only |
| `like` | no | yes | yes | no | yes | yes |
| `text_match` in filter | yes | no | no | no | yes | no |
| Filtered count | yes | yes | yes | yes | yes | yes |
| Scroll | yes | yes | yes | no | yes | yes |
| Introspection | typed | typed | none | none | typed | typed |
| Server-side embedding | no | no | no | no | yes | no |

**Every backend** accepts comparison ops: `eq` `ne` `gt` `gte` `lt` `lte` `in` `nin`.

**pgvector table mode** (`mode: table` or `vector_column: null`) is for lookup / count / scroll / pipeline only — no `kind: search` (`VB2016`).

Connection fields: [tools.yaml → connections](tools-yaml-reference.md#connections).

## Mixing stores

One YAML file can declare several connections with different backends. That is still **one** MCP server (`vectorsmith serve`). Each tool names `target.connection`. Two Claude connectors still mean two YAML files and two `serve --name` processes.

## Not a store extra

These extras are **agent SDKs**, not databases:

| Extra | For |
|---|---|
| `langchain` / `langgraph` | `load_tools` |
| `openai-agents` | `BoundTools.as_openai_agents()` |
| `anthropic` | `BoundTools.as_anthropic()` |

`connect()` only needs the store extra. Details: [Python API](python-api.md#extras).
