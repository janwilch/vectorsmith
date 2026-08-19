"""Typer entrypoint: serve, validate, introspect, test, init, drafts, approve, auth."""

from __future__ import annotations

from pathlib import Path

import typer

from vectorsmith_cli.drafts_cmd import run_approve, run_drafts
from vectorsmith_cli.identity import DEFAULT_SERVER_NAME
from vectorsmith_cli.init_cmd import run_init
from vectorsmith_cli.introspect_cmd import run_introspect
from vectorsmith_cli.serve_http import serve_http
from vectorsmith_cli.serve_stdio import serve_stdio
from vectorsmith_cli.test_cmd import run_test
from vectorsmith_cli.validate_cmd import run_validate

app = typer.Typer(name="vectorsmith", no_args_is_help=True)


@app.command()
def init(
    directory: Path = typer.Argument(Path("."), help="Where to write tools.yaml"),
    print_desktop_config: bool = typer.Option(False, "--print-desktop-config"),
    name: str = typer.Option(
        DEFAULT_SERVER_NAME,
        "--name",
        help="mcpServers key to print (you choose this in Claude / your SDK)",
    ),
) -> None:
    """Write an example tools.yaml and .env.example."""
    run_init(directory, print_desktop_config=print_desktop_config, name=name)


@app.command()
def validate(
    tools: Path = typer.Argument(..., help="Path to tools.yaml"),
    live: bool = typer.Option(False, "--live"),
    as_json: bool = typer.Option(False, "--json"),
    strict: bool = typer.Option(False, "--strict"),
    env_file: Path | None = typer.Option(None, "--env-file"),
) -> None:
    """Validate a TDS file."""
    raise SystemExit(
        run_validate(tools, live=live, as_json=as_json, strict=strict, env_file=env_file)
    )


@app.command("serve")
def serve_cmd(
    tools: Path = typer.Argument(..., help="Path to tools.yaml"),
    http: str | None = typer.Option(None, "--http", help="HOST:PORT for streamable HTTP"),
    auth: str = typer.Option("builtin", "--auth"),
    public_url: str | None = typer.Option(None, "--public-url"),
    env_file: Path | None = typer.Option(None, "--env-file"),
    enable_define: bool = typer.Option(False, "--enable-define"),
    watch: bool = typer.Option(True, "--watch/--no-watch"),
    name: str = typer.Option(
        DEFAULT_SERVER_NAME,
        "--name",
        help="MCP serverInfo.name; also the mcpServers key you set in Claude / your SDK",
    ),
) -> None:
    """Serve tools over MCP stdio or HTTP."""
    if http:
        serve_http(
            tools,
            bind=http,
            auth=auth,
            public_url=public_url,
            env_file=env_file,
            enable_define=enable_define,
            name=name,
        )
        return
    serve_stdio(
        tools, env_file=env_file, enable_define=enable_define, watch=watch, name=name
    )


@app.command("test")
def test_cmd(
    tools: Path = typer.Argument(...),
    tool: str = typer.Argument(...),
    args: str = typer.Option("{}", "--args"),
    show_plan: bool = typer.Option(False, "--show-plan"),
    env_file: Path | None = typer.Option(None, "--env-file"),
) -> None:
    """Smoke-test one compiled tool. Agents must call tools over MCP via serve."""
    raise SystemExit(run_test(tools, tool, args, show_plan=show_plan, env_file=env_file))


@app.command()
def introspect(
    tools: Path = typer.Argument(...),
    connection: str = typer.Option(..., "--connection"),
    out: Path = typer.Option(Path("schema.json"), "--out"),
    collections: str | None = typer.Option(None, "--collections"),
    redact_examples: bool = typer.Option(False, "--redact-examples"),
    audit: bool = typer.Option(False, "--audit"),
    env_file: Path | None = typer.Option(None, "--env-file"),
) -> None:
    """Export a metadata-only schema.json."""
    raise SystemExit(
        run_introspect(
            tools,
            connection=connection,
            out=out,
            collections=collections,
            redact_examples=redact_examples,
            audit=audit,
            env_file=env_file,
        )
    )


@app.command()
def drafts(
    action: str = typer.Argument(..., help="list | reject"),
    name: str | None = typer.Argument(None),
) -> None:
    """List or reject pending drafts."""
    run_drafts(action, name)


@app.command()
def approve(
    name: str = typer.Argument(...),
    file: Path = typer.Option(Path("tools.yaml"), "--file"),
) -> None:
    """Promote a draft into tools.yaml."""
    run_approve(name, file)


@app.command()
def auth(
    action: str = typer.Argument(..., help="rotate-secret | revoke"),
) -> None:
    """Builtin OAuth admin: rotate-secret | revoke."""
    from vectorsmith_cli.http.builtin_oauth.store import AuthStore

    store = AuthStore()
    if action == "rotate-secret":
        secret = store.rotate_secret()
        dest = store.write_secret_once(secret)
        print(f"New access secret written to {dest} (mode 0600)", file=__import__("sys").stderr)
        return
    if action == "revoke":
        store.revoke_all()
        print("All tokens revoked", file=__import__("sys").stderr)
        return
    print("usage: auth rotate-secret | revoke", file=__import__("sys").stderr)
    raise SystemExit(2)
