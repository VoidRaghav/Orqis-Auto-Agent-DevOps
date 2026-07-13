"""
FastAPI dependencies — resolve workspace from session, API key, or default.
"""

from __future__ import annotations

import hmac
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request, Response

from .. import config
from . import tenancy, workspace_auth
from .tenancy import DEFAULT_WORKSPACE_ID, set_workspace_id


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Orqis-Api-Key", "").strip()


def _session_cookie(request: Request) -> Optional[str]:
    raw = request.cookies.get(config.SESSION_COOKIE_NAME, "")
    return workspace_auth.verify_session_cookie(raw)


def actor_from_request(request: Request) -> str:
    """Best-effort actor label for audit entries."""
    session_id = _session_cookie(request)
    if session_id:
        return f"session:{session_id[:8]}"
    if request.headers.get("X-Orqis-Admin-Token"):
        return "admin_token"
    tok = _bearer_token(request)
    if tok.startswith("orqs_"):
        return f"api_key:{tok[:12]}"
    return "unknown"


async def bind_workspace(workspace_id: str) -> str:
    set_workspace_id(workspace_id)
    return workspace_id


async def resolve_ingest_workspace(request: Request) -> str:
    """
    Ingest: API key when multi-tenant; else default workspace (local dev).
  """
    if config.MULTI_TENANT:
        token = _bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="missing ingest API key")
        wid = await workspace_auth.resolve_workspace_from_api_key(token)
        if not wid:
            raise HTTPException(status_code=401, detail="invalid ingest API key")
        if config.INGEST_RATE_LIMIT_PER_MIN > 0:
            await _rate_limit_ingest(wid)
        return await bind_workspace(wid)
    return await bind_workspace(DEFAULT_WORKSPACE_ID)


async def resolve_dashboard_workspace(request: Request) -> str:
    """Dashboard reads: session cookie when multi-tenant; else default."""
    if config.MULTI_TENANT:
        session_id = _session_cookie(request)
        if not session_id:
            raise HTTPException(status_code=401, detail="not authenticated")
        session = await workspace_auth.get_session(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="session expired")
        wid = session["workspace_id"]
        github_id = session.get("github_id")
        if github_id is not None and not await workspace_auth.is_workspace_member(
            wid, int(github_id)
        ):
            raise HTTPException(status_code=403, detail="not a workspace member")
        return await bind_workspace(wid)
    return await bind_workspace(DEFAULT_WORKSPACE_ID)


async def resolve_write_auth(request: Request) -> str:
    """
    Writes: session (dashboard), workspace API key (hosted MCP), or admin token (local MT).
    """
    if config.MULTI_TENANT:
        session_id = _session_cookie(request)
        if session_id:
            session = await workspace_auth.get_session(session_id)
            if session:
                wid = session["workspace_id"]
                github_id = session.get("github_id")
                if github_id is not None and not await workspace_auth.is_workspace_member(
                    wid, int(github_id)
                ):
                    raise HTTPException(status_code=403, detail="not a workspace member")
                return await bind_workspace(wid)

        api_tok = _bearer_token(request)
        if api_tok.startswith("orqs_"):
            wid = await workspace_auth.resolve_workspace_from_api_key(api_tok)
            if wid:
                return await bind_workspace(wid)

        token = api_tok or request.headers.get("X-Orqis-Admin-Token", "")
        if token and config.ADMIN_TOKEN and hmac.compare_digest(token, config.ADMIN_TOKEN):
            if config.HOSTED:
                raise HTTPException(
                    status_code=401,
                    detail="admin token writes are disabled in hosted multi-tenant mode",
                )
            wid = request.headers.get("X-Orqis-Workspace", "")
            if not wid:
                raise HTTPException(
                    status_code=401,
                    detail="X-Orqis-Workspace header required for admin/MCP writes in multi-tenant mode",
                )
            return await bind_workspace(wid)

        raise HTTPException(status_code=401, detail="not authorized")
    # Legacy single-tenant: admin token or open when unset
    if config.ADMIN_TOKEN:
        header = request.headers.get("X-Orqis-Admin-Token", "")
        token = _bearer_token(request) or header
        if not token or not hmac.compare_digest(token, config.ADMIN_TOKEN):
            raise HTTPException(status_code=401, detail="invalid or missing admin token")
    return await bind_workspace(DEFAULT_WORKSPACE_ID)


async def resolve_ws_workspace(request: Request, ticket: str = "") -> str:
    """WebSocket: signed ticket query param or session cookie."""
    if config.MULTI_TENANT:
        if ticket:
            wid = await _verify_ws_ticket_async(ticket)
            if wid:
                return await bind_workspace(wid)
        session_id = _session_cookie(request)
        if session_id:
            session = await workspace_auth.get_session(session_id)
            if session:
                return await bind_workspace(session["workspace_id"])
        raise HTTPException(status_code=401, detail="websocket not authenticated")
    return await bind_workspace(DEFAULT_WORKSPACE_ID)


def set_session_cookie(response: Response, session_id: str) -> None:
    signed = workspace_auth.sign_session_cookie(session_id)
    # Dashboard (Vercel) and backend (Render) are different sites, so the session
    # cookie must be SameSite=None to be sent on cross-site fetches — which the
    # browser only allows when Secure. Fall back to Lax for same-origin local dev.
    samesite = "none" if config.SESSION_COOKIE_SECURE else "lax"
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=signed,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite=samesite,
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/")


async def _rate_limit_ingest(workspace_id: str) -> None:
    from .store import get_redis

    r = await get_redis()
    bucket = f"orqis:ratelimit:{workspace_id}:{int(time.time()) // 60}"
    count = await r.incr(bucket)
    if count == 1:
        await r.expire(bucket, 120)
    if count > config.INGEST_RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="ingest rate limit exceeded")


async def create_ws_ticket_async(workspace_id: str) -> str:
    import hashlib

    from .store import get_redis

    nonce = secrets.token_hex(16)
    r = await get_redis()
    await r.set(f"orqis:ws_ticket:{nonce}", workspace_id, ex=60)
    secret = config.SESSION_SECRET.encode()
    ts = str(int(time.time()))
    payload = f"{workspace_id}.{ts}.{nonce}"
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


async def _verify_ws_ticket_async(ticket: str) -> Optional[str]:
    import hashlib

    from .store import get_redis

    try:
        payload, sig = ticket.rsplit(".", 1)
        workspace_id, ts_str, nonce = payload.rsplit(".", 2)
        if int(time.time()) - int(ts_str) > 60:
            return None
        secret = config.SESSION_SECRET.encode()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        r = await get_redis()
        key = f"orqis:ws_ticket:{nonce}"
        stored = await r.get(key)
        if not stored or stored != workspace_id:
            return None
        await r.delete(key)
        return workspace_id
    except Exception:
        return None


def _verify_ws_ticket(ticket: str) -> Optional[str]:
    """Deprecated sync path — use _verify_ws_ticket_async from async handlers."""
    import asyncio

    return asyncio.run(_verify_ws_ticket_async(ticket))
