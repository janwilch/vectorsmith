"""HTTP serve (streamable MCP + builtin OAuth)."""

from __future__ import annotations

import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vectorsmith_cli.http.app import build_app
from vectorsmith_cli.http.auth.resolve import build_auth_provider, merge_api_key_cfg, merge_jwt_cfg
from vectorsmith_cli.http.builtin_oauth.store import AuthStore
from vectorsmith_cli.identity import DEFAULT_SERVER_NAME
from vectorsmith_cli.observe.logging import configure_logging
from vectorsmith_cli.observe.sinks import build_audit_sink
from vectorsmith_cli.serve_router import (
    ProjectRouter,
    configure_observability,
    configure_observability_many,
    load_engines,
    project_name,
)
from vectorsmith_cli.validate_cmd import _load_env
from vectorsmith_core.api import load_project
from vectorsmith_core.embed.provider import FastEmbedProvider
from vectorsmith_core.execute.engine import Engine
from vectorsmith_core.security.credentials import build_credential_resolver
from vectorsmith_core.security.hardening import (
    apply_serve_hardening_many,
    serve_hardening_errors,
)


def localhost_bind(bind: str) -> bool:
    return bind.startswith("127.0.0.1") or bind.startswith("localhost")


def _fail_issues(project: Any) -> None:
    errors = [i for i in project.issues if i.severity == "error"]
    if errors:
        for i in errors:
            print(f"{i.code}: {i.message}", file=sys.stderr)
        raise SystemExit(2)


def _fail_hardening(project: Any) -> None:
    for msg in serve_hardening_errors(project.tds):
        print(msg, file=sys.stderr)
        raise SystemExit(2)


def serve_http(
    tools: Path | Sequence[Path],
    *,
    bind: str,
    auth: str,
    public_url: str | None,
    env_file: Path | None,
    enable_define: bool = False,
    include_meta: bool = True,
    live_embed: bool = False,
    name: str = DEFAULT_SERVER_NAME,
    jwt_issuer: str | None = None,
    jwt_audience: str | None = None,
    jwks_url: str | None = None,
    api_keys_file: Path | None = None,
    auth_store: str = "sqlite",
    redis_url: str | None = None,
    audit_log: Path | None = None,
    audit_sink: str | None = None,
    audit_url: str | None = None,
    route_by_claim: str | None = None,
    default_project: str | None = None,
    shutdown_grace_s: int = 30,
    log_format: str = "text",
    log_level: str = "info",
) -> None:
    if auth == "none" and not localhost_bind(bind):
        print("--auth none is only allowed on localhost", file=sys.stderr)
        raise SystemExit(3)
    if auth == "builtin" and (not public_url or not public_url.startswith("https://")):
        print("builtin auth requires https --public-url", file=sys.stderr)
        raise SystemExit(2)

    host, _, port_s = bind.rpartition(":")
    host = host or "127.0.0.1"
    port = int(port_s or "8000")
    configure_logging(log_format, log_level)
    env = _load_env(env_file)
    paths = [tools] if isinstance(tools, Path) else list(tools)
    try:
        embed: FastEmbedProvider | None = FastEmbedProvider()
    except Exception:
        embed = None
    resolver = build_credential_resolver(env)
    cli_audit = audit_log is not None or audit_sink is not None or audit_url is not None
    if len(paths) == 1:
        project = load_project(paths[0], env=env)
        _fail_issues(project)
        _fail_hardening(project)
        engine = Engine(
            project,
            credential_resolver=resolver,
            embed_provider=embed,
            audit_sink=build_audit_sink(
                project.tds.observability.audit,
                log_path=audit_log,
                sink_name=audit_sink,
                url=audit_url,
            ),
        )
        router = None
    else:
        default = default_project or project_name(paths[0])
        shared_sink = None
        make_sink = None
        if cli_audit:
            shared_sink = build_audit_sink(
                load_project(paths[0], env=env).tds.observability.audit,
                log_path=audit_log,
                sink_name=audit_sink,
                url=audit_url,
            )
        else:

            def make_sink(project: Any) -> Any:
                return build_audit_sink(project.tds.observability.audit)

        engines = load_engines(
            paths,
            env=env,
            credential_resolver=resolver,
            embed_provider=embed,
            audit_sink=shared_sink,
            make_audit_sink=make_sink,
        )
        router = ProjectRouter(engines, route_claim=route_by_claim, default=default)
        engine = engines[default]
        for part in engines.values():
            _fail_hardening(part.project)
    if router is not None:
        configure_observability_many(list(router.engines.values()))
        enable_define, include_meta = apply_serve_hardening_many(
            [e.project.tds for e in router.engines.values()],
            enable_define=enable_define,
            include_meta=include_meta,
        )
    else:
        configure_observability(engine)
        enable_define, include_meta = apply_serve_hardening_many(
            [engine.project.tds],
            enable_define=enable_define,
            include_meta=include_meta,
        )
    yaml_auth = engine.project.tds.security.auth
    jwt_cfg = merge_jwt_cfg(
        yaml_auth.jwt, issuer=jwt_issuer, audience=jwt_audience, jwks_url=jwks_url
    )
    api_cfg = merge_api_key_cfg(yaml_auth.api_key, keys_file=api_keys_file)
    if auth == "jwt" and not jwt_cfg.jwks_url:
        print("jwt auth requires --jwks-url or security.auth.jwt.jwks_url", file=sys.stderr)
        raise SystemExit(2)
    if auth == "api_key" and not api_cfg.keys_file:
        print(
            "api_key auth requires --api-keys-file or security.auth.api_key.keys_file",
            file=sys.stderr,
        )
        raise SystemExit(2)
    store: Any
    if auth_store == "redis" and not redis_url:
        print("--auth-store redis requires --redis-url", file=sys.stderr)
        raise SystemExit(2)
    if auth_store == "redis":
        from vectorsmith_cli.http.auth.store.redis import RedisAuthStore

        store = RedisAuthStore(redis_url)
    else:
        store = AuthStore()
    if auth == "builtin":
        secret = store.bootstrap_secret()
        if secret:
            dest = store.write_secret_once(secret)
            print(f"Access secret written to {dest} (mode 0600; shown once)", file=sys.stderr)
    provider = build_auth_provider(
        auth,
        store=store,
        auth_cfg=yaml_auth,
        jwt_cfg=jwt_cfg,
        api_key_cfg=api_cfg,
    )
    app = build_app(
        engine=engine,
        enable_define=enable_define,
        include_meta=include_meta,
        auth=auth,
        public_url=public_url or f"http://{bind}",
        store=store,
        drafts_path=Path("tools.drafts.yaml"),
        name=name,
        live_embed=live_embed,
        auth_provider=provider,
        router=router,
        metrics_enabled=engine.project.tds.observability.metrics.enabled,
    )

    def _begin_drain(*_args: object) -> None:
        app.state.draining = True

    signal.signal(signal.SIGTERM, _begin_drain)
    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        timeout_graceful_shutdown=shutdown_grace_s,
    )
