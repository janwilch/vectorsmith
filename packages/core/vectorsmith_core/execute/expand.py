"""Optional query expansion. Disabled by default; failures fall back."""

from __future__ import annotations

import json
from typing import Any, Protocol


class ExpandProvider(Protocol):
    async def expand(self, query: str, *, spec: Any) -> list[str]: ...


class _NoneExpand:
    async def expand(self, query: str, *, spec: Any) -> list[str]:
        return []


class _OpenAIExpand:
    async def expand(self, query: str, *, spec: Any) -> list[str]:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai extra required for query.expand") from exc
        cfg = dict(getattr(spec, "config", {}) or {})
        n = int(getattr(spec, "variants", 3))
        prompt = str(
            cfg.get("prompt")
            or (
                "Rewrite this search query into {variants} diverse search phrases.\n"
                "Query: {query}\nReturn JSON array of strings."
            )
        ).format(variants=n, query=query)
        client = AsyncOpenAI(
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url") or None,
        )
        resp = await client.chat.completions.create(
            model=str(getattr(spec, "model", None) or "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        return _parse_phrases(text)


class _HTTPExpand:
    async def expand(self, query: str, *, spec: Any) -> list[str]:
        import httpx

        cfg = dict(getattr(spec, "config", {}) or {})
        url = cfg.get("base_url") or cfg.get("url")
        if not url:
            raise RuntimeError("query.expand http provider needs config.base_url")
        headers = dict(cfg.get("headers") or {})
        if cfg.get("api_key"):
            headers.setdefault("Authorization", f"Bearer {cfg['api_key']}")
        async with httpx.AsyncClient(timeout=float(cfg.get("timeout_s") or 30)) as client:
            resp = await client.post(
                str(url),
                json={"query": query, "variants": int(getattr(spec, "variants", 3))},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list):
            return [str(x) for x in data]
        phrases = data.get("phrases") or data.get("variants") or data.get("queries") or []
        return [str(x) for x in phrases]


def resolve_expand_provider(name: str) -> ExpandProvider:
    if name == "openai":
        return _OpenAIExpand()
    if name == "http":
        return _HTTPExpand()
    return _NoneExpand()


def _parse_phrases(text: str) -> list[str]:
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        for key in ("phrases", "variants", "queries"):
            if key in data and isinstance(data[key], list):
                return [str(x) for x in data[key]]
    return []


async def expand_query(text: str, spec: Any) -> tuple[list[str], str | None]:
    if spec is None or not getattr(spec, "enabled", False):
        return [text], None
    hook = getattr(spec, "_expand", None)
    try:
        if hook is not None:
            extras = await hook(text, spec=spec)
        else:
            extras = await resolve_expand_provider(getattr(spec, "provider", "none")).expand(
                text, spec=spec
            )
        seen = {text}
        variants = [text]
        for item in extras:
            phrase = str(item).strip()
            if phrase and phrase not in seen:
                seen.add(phrase)
                variants.append(phrase)
        cap = int(getattr(spec, "variants", 3))
        return variants[: cap + 1], None
    except Exception:
        return [text], "VB4030"
