"""Create the `tickets` collection on the live Qdrant and upsert sample rows.

Same embedding space as invoices: 384-dim BAAI/bge-small-en-v1.5 cosine over `body`.
Tenant is always `acme` (matches tools.yaml static filters).
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env" if (HERE / ".env").exists() else HERE / ".env.example"

N = 80
CUSTOMERS = [
    "Globex",
    "Initech",
    "Umbrella",
    "Müller GmbH",
    "山田商事",
    "O'Brien & Co",
]
STATUSES = ["open", "pending", "resolved", "closed"]
SEVERITIES = ["low", "medium", "high", "critical"]
PRODUCTS = ["billing", "api", "dashboard", "auth"]

BODIES = [
    "Cannot download the overdue invoice PDF from the billing portal.",
    "Payment receipt never arrived after the invoice was marked paid.",
    "SSO login loops on the dashboard after password reset.",
    "API returns 429 when the billing webhook retries the same invoice.",
    "Customer cannot filter invoices by status in the dashboard.",
    "Auth token expires while uploading a large invoice attachment.",
    "Critical: checkout fails for unicode client names on the invoice page.",
    "Pending refund for a duplicate Globex invoice still shows as overdue.",
]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def docs() -> list[dict]:
    out = []
    for i in range(1, N + 1):
        status = STATUSES[i % len(STATUSES)]
        severity = SEVERITIES[(i // len(STATUSES)) % len(SEVERITIES)]
        product = PRODUCTS[(i // (len(STATUSES) * len(SEVERITIES))) % len(PRODUCTS)]
        customer = CUSTOMERS[(i - 1) % len(CUSTOMERS)]
        template = BODIES[(i - 1) % len(BODIES)]
        body = f"Ticket TKT-{i:04d} for {customer}: {template}"
        out.append(
            {
                "ticket_id": f"TKT-{i:04d}",
                "customer_name": customer,
                "status": status,
                "severity": severity,
                "product": product,
                "tenant": "acme",
                "body": body,
            }
        )
    return out


def client_for(url: str, api_key: str | None) -> QdrantClient:
    parsed = urlparse(url)
    if parsed.port is not None:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 6333
    return QdrantClient(
        url=url,
        api_key=api_key or None,
        port=port,
        prefer_grpc=False,
        timeout=60,
        check_compatibility=False,
    )


def main() -> int:
    env = load_env(ENV_FILE)
    url = env.get("QDRANT_URL")
    if not url:
        print("QDRANT_URL is unset", file=sys.stderr)
        return 2

    from fastembed import TextEmbedding

    rows = docs()
    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    vectors = list(embedder.embed([row["body"] for row in rows]))

    qdrant = client_for(url, env.get("QDRANT_API_KEY"))
    if qdrant.collection_exists("tickets"):
        qdrant.delete_collection("tickets")
    qdrant.create_collection(
        collection_name="tickets",
        vectors_config=qm.VectorParams(size=384, distance=qm.Distance.COSINE),
    )
    for field in ("tenant", "customer_name", "status", "severity", "product", "ticket_id"):
        qdrant.create_payload_index(
            collection_name="tickets",
            field_name=field,
            field_schema=qm.PayloadSchemaType.KEYWORD,
        )

    points = [
        qm.PointStruct(id=i, vector=list(map(float, vec)), payload=row)
        for i, (row, vec) in enumerate(zip(rows, vectors, strict=True), start=1)
    ]
    qdrant.upsert(collection_name="tickets", points=points, wait=True)
    info = qdrant.get_collection("tickets")
    print(f"tickets: {info.points_count} points on {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
