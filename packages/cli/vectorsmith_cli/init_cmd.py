"""init — write example tools.yaml and .env.example."""

from __future__ import annotations

from pathlib import Path

from vectorsmith_cli.identity import DEFAULT_SERVER_NAME

EXAMPLE = """\
tds_version: "1"

connections:
  main:
    backend: qdrant
    url: ${QDRANT_URL:-http://localhost:6333}
    api_key: ${QDRANT_API_KEY:-}
    builtin_tools:
      semantic_search: true
      get_by_id: true
      list_collections: true
    builtin_defaults:
      collections: [invoices]

defaults:
  embedding: fastembed/BAAI/bge-small-en-v1.5

# authoring:
#   define_tool: true

tools:
  - name: search_invoices
    kind: search
    description: >
      Search invoices by free text and filter by client, status and due date.
      Use when the user asks about invoices, billing or payments.
    target: { connection: main, collection: invoices }
    query: { param: query, required: false }
    parameters:
      - { name: client, path: client_name, dtype: keyword, op: eq }
      - { name: status, path: status, dtype: keyword, op: in,
          enum: [draft, sent, paid, overdue] }
    output:
      fields: [invoice_id, client_name, status, amount]
      limit_default: 10
      limit_max: 50
"""

ENV = """\
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
"""

DESKTOP = """\
{{
  "mcpServers": {{
    "{name}": {{
      "command": "uv",
      "args": [
        "run", "--directory", "{cwd}", "vectorsmith",
        "serve", "{tools}", "--env-file", "{env}", "--name", "{name}"
      ],
      "cwd": "{cwd}",
      "env": {{
        "QDRANT_URL": "http://localhost:6333"
      }}
    }},
    "filesystem": {{
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "{cwd}"]
    }}
  }}
}}
"""


def run_init(
    directory: Path,
    *,
    print_desktop_config: bool = False,
    name: str = DEFAULT_SERVER_NAME,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    tools = directory / "tools.yaml"
    if not tools.exists():
        tools.write_text(EXAMPLE)
    env = directory / ".env.example"
    if not env.exists():
        env.write_text(ENV)
    if print_desktop_config:
        print(
            DESKTOP.format(
                name=name,
                cwd=directory.resolve(),
                tools=str(tools.resolve()),
                env=str(env.resolve()),
            ),
            end="",
        )
    else:
        print(f"Wrote {tools} and {env}", flush=True)
