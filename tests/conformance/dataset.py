"""Shared 1000-doc conformance dataset (seed=42)."""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

N = 1000
SEED = 42

CLIENTS = [
    "Globex",
    "Initech",
    "Umbrella",
    "Müller GmbH",
    "山田商事",
    "O'Brien & Co",
]


def generate_docs(n: int = N, seed: int = SEED) -> list[dict[str, Any]]:
    rng = random.Random(seed)  # noqa: S311 — deterministic fixture, not crypto
    rare = set(rng.sample(range(1, n + 1), max(1, n // 20)))
    docs = []
    for i in range(1, n + 1):
        status = rng.choice(["draft", "sent", "paid", "overdue"])
        docs.append(
            {
                "invoice_id": f"INV-{i:04d}",
                "client_name": CLIENTS[(i - 1) % len(CLIENTS)],
                "status": status,
                "due_date": (date(2024, 1, 1) + timedelta(days=rng.randint(0, 800))).isoformat(),
                "amount": round(rng.uniform(100, 20000), 2),
                "rare_flag": i in rare,
                "tenant": "acme",
                "body": f"Invoice INV-{i:04d}",
            }
        )
    return docs
