"""HTTP serve (streamable MCP + builtin OAuth)."""

from __future__ import annotations

import sys
from pathlib import Path

from vectorsmith_cli.http.app import build_app
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_cli.identity import DEFAULT_SERVER_NAME
from vectorsmith_cli.validate_cmd import _load_env
from vectorsmith_core.api import EnvCredentialResolver, load_project
from vectorsmith_core.embed.provider import FastEmbedProvider
from vectorsmith_core.execute.engine import Engine


def serve_http(
    tools: Path,
    *,
    bind: str,
    auth: str,
    public_url: str | None,
    env_file: Path | None,
    enable_define: bool = False,
    name: str = DEFAULT_SERVER_NAME,
) -> None:
    if auth == "none" and not bind.startswith("127.0.0.1") and not bind.startswith("localhost"):
        print("--auth none is only allowed on localhost", file=sys.stderr)
        raise SystemExit(3)
    if auth == "builtin" and (not public_url or not public_url.startswith("https://")):
        print("builtin auth requires https --public-url", file=sys.stderr)
        raise SystemExit(2)

    host, _, port_s = bind.rpartition(":")
    host = host or "127.0.0.1"
    port = int(port_s or "8000")
    env = _load_env(env_file)
    project = load_project(tools, env=env)
    errors = [i for i in project.issues if i.severity == "error"]
    if errors:
        for i in errors:
            print(f"{i.code}: {i.message}", file=sys.stderr)
        raise SystemExit(2)
    try:
        embed: FastEmbedProvider | None = FastEmbedProvider()
    except Exception:
        embed = None
    engine = Engine(project, credential_resolver=EnvCredentialResolver(env), embed_provider=embed)
    store = AuthStore()
    if auth == "builtin":
        secret = store.bootstrap_secret()
        if secret:
            print(f"Access secret (shown once): {secret}", file=sys.stderr)
    app = build_app(
        engine=engine,
        enable_define=enable_define,
        auth=auth,
        public_url=public_url or f"http://{bind}",
        store=store,
        drafts_path=Path("tools.drafts.yaml"),
        name=name,
    )
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
