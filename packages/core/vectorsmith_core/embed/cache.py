"""LRU embed cache keyed by (provider, model, text_hash)."""

from __future__ import annotations

import hashlib
import os
import time
from collections import OrderedDict


def _default_size() -> int:
    raw = os.environ.get("VECTORSMITH_EMBED_CACHE_SIZE", "10000")
    try:
        return max(0, int(raw))
    except ValueError:
        return 10_000


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbedCache:
    def __init__(self, maxsize: int | None = None, ttl_s: float | None = None) -> None:
        self.maxsize = _default_size() if maxsize is None else maxsize
        self.ttl_s = ttl_s
        self._data: OrderedDict[tuple[str, str, str], tuple[list[float], float]] = (
            OrderedDict()
        )

    def get(self, provider: str, model: str, text: str) -> list[float] | None:
        key = (provider, model, text_hash(text))
        hit = self._data.get(key)
        if hit is None:
            return None
        vec, ts = hit
        if self.ttl_s is not None and time.monotonic() - ts > self.ttl_s:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return vec

    def put(self, provider: str, model: str, text: str, vec: list[float]) -> None:
        if self.maxsize <= 0:
            return
        key = (provider, model, text_hash(text))
        self._data[key] = (vec, time.monotonic())
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)
