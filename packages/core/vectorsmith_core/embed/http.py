"""Generic HTTP embedding gateway."""

from __future__ import annotations

from typing import Any

from vectorsmith_core.embed.cache import EmbedCache
from vectorsmith_core.embed.models import resolve_dims
from vectorsmith_core.errors import EmbeddingError
from vectorsmith_core.tds.models import EmbeddingConfig


def _extract_vectors(payload: Any, path: str) -> list[list[float]]:
    if path == "data[*].embedding" and isinstance(payload, dict):
        rows = payload.get("data") or []
        return [[float(x) for x in row["embedding"]] for row in rows]
    current: Any = payload
    star_applied = False
    for part in path.split("."):
        if part.endswith("[*]"):
            key = part[:-3]
            if key:
                current = current[key]
            if not isinstance(current, list):
                raise EmbeddingError(detail=f"response path '{path}' is not a list")
            star_applied = True
            rest_after: list[str] = []
            # remaining parts applied per element below
            idx = path.split(".").index(part)
            rest_after = path.split(".")[idx + 1 :]
            out: list[list[float]] = []
            for item in current:
                node: Any = item
                for rp in rest_after:
                    node = node[rp]
                out.append([float(x) for x in node])
            return out
        current = current[part]
    if star_applied:
        raise EmbeddingError(detail=f"unusable response path '{path}'")
    if isinstance(current, list) and current and isinstance(current[0], list):
        return [[float(x) for x in row] for row in current]
    raise EmbeddingError(detail=f"cannot read vectors from response path '{path}'")


class HttpEmbedProvider:
    name = "http"

    def __init__(self) -> None:
        self._cache = EmbedCache()

    def dims(self, model: str, *, config: EmbeddingConfig | None = None) -> int:
        return resolve_dims(model, config)

    async def health(self) -> bool:
        return True

    async def embed(
        self,
        texts: list[str],
        model: str,
        *,
        config: EmbeddingConfig | None = None,
    ) -> list[list[float]]:
        cfg = dict(config.config) if config is not None else {}
        ttl = cfg.get("cache_ttl_s")
        cache = EmbedCache(ttl_s=float(ttl)) if ttl is not None else self._cache
        out: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str]] = []
        for i, text in enumerate(texts):
            hit = cache.get(self.name, model, text)
            if hit is None:
                missing.append((i, text))
            else:
                out[i] = hit
        if not missing:
            return [v for v in out if v is not None]
        base_url = str(cfg.get("base_url") or "")
        if not base_url:
            raise EmbeddingError(detail="http embed provider requires config.base_url")
        batch_size = int(cfg.get("batch_size") or 32)
        raw_req = cfg.get("request")
        req: dict[str, Any] = raw_req if isinstance(raw_req, dict) else {}
        model_field = str(req.get("model_field") or "model")
        input_field = str(req.get("input_field") or "input")
        raw_resp = cfg.get("response")
        resp_cfg: dict[str, Any] = raw_resp if isinstance(raw_resp, dict) else {}
        vectors_path = str(resp_cfg.get("vectors_path") or "data[*].embedding")
        headers = dict(cfg.get("headers") or {})
        api_key = cfg.get("api_key")
        if api_key and "authorization" not in {k.lower() for k in headers}:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = float(cfg.get("timeout_s") or 120)
        try:
            import httpx
        except ImportError as exc:
            raise EmbeddingError(detail="httpx is required for the http embed provider") from exc
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for start in range(0, len(missing), batch_size):
                    chunk = missing[start : start + batch_size]
                    body = {
                        model_field: model,
                        input_field: [t for _i, t in chunk],
                    }
                    res = await client.post(base_url, json=body, headers=headers)
                    res.raise_for_status()
                    vecs = _extract_vectors(res.json(), vectors_path)
                    if len(vecs) != len(chunk):
                        raise EmbeddingError(
                            detail="http embed response length does not match input"
                        )
                    for (idx, text), vec in zip(chunk, vecs, strict=True):
                        cache.put(self.name, model, text, vec)
                        out[idx] = vec
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(detail=str(exc)) from exc
        return [v if v is not None else [] for v in out]
