"""OAuth routes: authorize, token, register, revoke."""

from __future__ import annotations

from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from vectorsmith_cli.http.builtin_oauth.pages import AUTHORIZE_PAGE
from vectorsmith_cli.http.builtin_oauth.store import AuthStore

DCR_WINDOW = 3600
DCR_LIMIT = 10


class RateLimit:
    def __init__(self) -> None:
        self.hits: dict[str, list[float]] = {}

    def allow(self, ip: str) -> bool:
        import time

        now = time.time()
        bucket = [t for t in self.hits.get(ip, []) if now - t < DCR_WINDOW]
        if len(bucket) >= DCR_LIMIT:
            self.hits[ip] = bucket
            return False
        bucket.append(now)
        self.hits[ip] = bucket
        return True


_rate = RateLimit()


def well_known(public_url: str) -> dict:
    base = public_url.rstrip("/")
    return {
        "resource": base,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    }


def as_metadata(public_url: str) -> dict:
    base = public_url.rstrip("/")
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
    }


async def authorize(request: Request) -> Response:
    store: AuthStore = request.app.state.store
    if request.method == "GET":
        q = request.query_params
        if q.get("code_challenge_method") not in {None, "S256"}:
            return JSONResponse({"error": "S256 required"}, status_code=400)
        html = AUTHORIZE_PAGE.format(
            client_id=q.get("client_id", ""),
            redirect_uri=q.get("redirect_uri", ""),
            state=q.get("state", ""),
            code_challenge=q.get("code_challenge", ""),
        )
        return HTMLResponse(html)
    form = await request.form()
    secret = str(form.get("secret") or "")
    if not store.verify_secret(secret):
        return HTMLResponse("invalid secret", status_code=401)
    redirect_uri = str(form.get("redirect_uri") or "")
    code = store.issue_code(
        str(form.get("client_id") or ""),
        redirect_uri,
        str(form.get("code_challenge") or ""),
    )
    qs = urlencode({"code": code, "state": str(form.get("state") or "")})
    return RedirectResponse(f"{redirect_uri}?{qs}", status_code=302)


async def token(request: Request) -> Response:
    store: AuthStore = request.app.state.store
    form = await request.form()
    grant = str(form.get("grant_type") or "")
    if grant == "refresh_token":
        rotated = store.rotate_refresh(str(form.get("refresh_token") or ""))
        if rotated is None:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return JSONResponse(rotated)
    if grant != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    ok = store.consume_code(
        str(form.get("code") or ""),
        str(form.get("code_verifier") or ""),
        str(form.get("redirect_uri") or ""),
    )
    if not ok:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    return JSONResponse(store.issue_tokens())


async def register(request: Request) -> Response:
    store: AuthStore = request.app.state.store
    ip = request.client.host if request.client else "unknown"
    if not _rate.allow(ip):
        return JSONResponse({"error": "slow_down"}, status_code=429)
    body = await request.json()
    uris = body.get("redirect_uris") or []
    if not uris:
        return JSONResponse({"error": "invalid_client"}, status_code=400)
    client_id = store.register_client(str(uris[0]))
    return JSONResponse({"client_id": client_id, "redirect_uris": uris}, status_code=201)


async def revoke(request: Request) -> Response:
    store: AuthStore = request.app.state.store
    store.revoke_all()
    return Response(status_code=200)
