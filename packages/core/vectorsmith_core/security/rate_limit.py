"""In-process and Redis rate limiters. Disabled unless ``security.rate_limit.enabled``."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Protocol

from vectorsmith_core.api import CallContext
from vectorsmith_core.errors import RateLimited
from vectorsmith_core.tds.models import RateLimitConfig


class RateLimiter(Protocol):
    async def check(self, key: str, limit: int, window_s: int) -> None: ...


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    async def check(self, key: str, limit: int, window_s: int) -> None:
        now = time.time()
        hits = [t for t in self._hits.get(key, []) if now - t < window_s]
        if limit > 0 and len(hits) >= limit:
            oldest = hits[0] if hits else now
            retry = max(1, int(window_s - (now - oldest)) + 1)
            raise RateLimited(
                detail=f"{limit} requests per {window_s}s exceeded",
                retry_after_s=retry,
            )
        hits.append(now)
        self._hits[key] = hits


class RedisRateLimiter:
    def __init__(self, url: str | None = None, *, client: Any = None) -> None:
        if client is not None:
            self._r = client
        else:
            try:
                import redis.asyncio as redis_async
            except ImportError as exc:
                raise RuntimeError(
                    "redis extra not installed: pip install 'vectorsmith[auth-redis]'"
                ) from exc
            if not url:
                raise RuntimeError("rate_limit.redis_url is required for store: redis")
            self._r = redis_async.Redis.from_url(url, decode_responses=True)
        incr = getattr(type(self._r), "incr", None)
        self._async = inspect.iscoroutinefunction(incr)

    def _bump_sync(self, rkey: str, window_s: int) -> tuple[int, int]:
        n = int(self._r.incr(rkey))
        if n == 1:
            self._r.expire(rkey, window_s)
        ttl = self._r.ttl(rkey)
        retry = int(ttl) if isinstance(ttl, int) and ttl > 0 else window_s
        return n, retry

    async def check(self, key: str, limit: int, window_s: int) -> None:
        rkey = f"vectorsmith:rl:{key}"
        if self._async:
            n = int(await self._r.incr(rkey))
            if n == 1:
                await self._r.expire(rkey, window_s)
            ttl = await self._r.ttl(rkey)
            retry = int(ttl) if isinstance(ttl, int) and ttl > 0 else window_s
        else:
            n, retry = await asyncio.to_thread(self._bump_sync, rkey, window_s)
        if limit > 0 and n > limit:
            raise RateLimited(
                detail=f"{limit} requests per {window_s}s exceeded",
                retry_after_s=retry,
            )


def parse_tool_rate(spec: str) -> tuple[int, int]:
    raw = spec.strip()
    if "/" not in raw:
        return int(raw), 60
    count_s, _, unit = raw.partition("/")
    unit = unit.strip().lower()
    window = 3600 if unit in {"hour", "hr", "h"} else 60
    return int(count_s), window


def build_rate_limiter(cfg: RateLimitConfig, *, client: Any = None) -> RateLimiter | None:
    if not cfg.enabled:
        return None
    if cfg.store == "redis":
        return RedisRateLimiter(cfg.redis_url, client=client)
    return MemoryRateLimiter()


async def enforce_rate_limits(
    limiter: RateLimiter,
    cfg: RateLimitConfig,
    ctx: CallContext,
    tool: str,
    *,
    embed: bool = False,
    llm: bool = False,
) -> None:
    principal = ctx.principal or "anonymous"
    glo = cfg.global_limits.requests_per_minute
    if glo:
        await limiter.check("__global__", glo, 60)
    per = cfg.per_principal
    if embed and per.embed_requests_per_minute:
        await limiter.check(f"{principal}:embed", per.embed_requests_per_minute, 60)
        return
    if llm and per.llm_requests_per_minute:
        await limiter.check(f"{principal}:llm", per.llm_requests_per_minute, 60)
        return
    if per.requests_per_minute:
        await limiter.check(f"{principal}:*", per.requests_per_minute, 60)
    if tool in cfg.per_tool:
        limit, window = parse_tool_rate(cfg.per_tool[tool])
        try:
            await limiter.check(f"{principal}:{tool}", limit, window)
        except RateLimited as exc:
            raise RateLimited(
                detail=f"{limit} requests per minute exceeded for {tool}",
                retry_after_s=exc.retry_after_s,
            ) from exc
