"""
Orqis backend server.

Endpoints:
  POST /drain                        - Universal log drain (any format, any source)
  POST /ingest                       - Structured batch ingest (lines array)
  POST /events                       - Single LogEvent from local daemon
  PATCH /events/{id}/interpretation  - Async LLM interpretation update
  GET  /events                       - Recent events for dashboard initial load
  POST /trace                        - SDK instrumentation trace event
  GET  /traces                       - Recent trace events
  GET  /incidents                    - Recent incidents
  GET  /incidents/{id}               - Single incident
  POST /incidents/{id}/approve       - Apply patch to disk
  POST /incidents/{id}/dismiss       - Dismiss incident
  GET  /incidents/{id}/prompt        - Copy-paste prompt for AI coding assistants
  WS   /ws                           - WebSocket for real-time dashboard updates
  GET  /health                       - Health check

Railway setup:
  Settings -> Log Drains -> Add Drain -> HTTP -> https://your-backend/drain?source=my-app
"""

import asyncio
import hmac
import json
import secrets
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .. import config
from ..backend import deps, store, ws_manager, workspace_auth
from ..backend import audit
from ..backend.tenancy import get_workspace_id, reset_workspace_id, set_workspace_id
from ..backend.models import ChangeLogEntry, Incident, IncidentStatus, IngestRequest, InterpretationUpdate, LogEvent, TraceEvent
from ..daemon import log_reader, normalizer


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify Redis is reachable at startup — fail fast with a clear error
    r = await store.get_redis()
    try:
        await r.ping()
    except Exception as e:
        raise RuntimeError(
            f"[orqis] cannot reach Redis at {config.REDIS_URL}: {e}\n"
            "Start Redis with:  redis-server  or  brew services start redis"
        ) from e

    migrated = await workspace_auth.migrate_legacy_keys_to_default_workspace()
    if any(migrated.values()):
        print(f"[orqis] migrated legacy Redis keys to default workspace: {migrated}")

    if config.MULTI_TENANT and not config.GITHUB_OAUTH_CLIENT_ID:
        print("[orqis] warning: ORQIS_MULTI_TENANT=1 but GITHUB_OAUTH_CLIENT_ID is unset")

    if config.MULTI_TENANT and config.HOSTED:
        if config.DEV_MODE:
            raise RuntimeError(
                "[orqis] ORQIS_DEV_MODE must be 0 when ORQIS_MULTI_TENANT=1 and ORQIS_HOSTED=1"
            )
        if config.SESSION_SECRET in ("", "orqis-dev-session-change-me"):
            raise RuntimeError(
                "[orqis] set ORQIS_SESSION_SECRET to a random value for hosted multi-tenant"
            )
        if not config.GITHUB_OAUTH_CLIENT_ID or not config.GITHUB_OAUTH_CLIENT_SECRET:
            raise RuntimeError(
                "[orqis] GITHUB_OAUTH_CLIENT_ID/SECRET required for hosted multi-tenant"
            )

    config.validate_multi_tenant_startup()

    from ..daemon import interpreter

    llm = await interpreter.check_readiness()
    if not llm.get("ok"):
        print(f"[orqis] warning: LLM not ready ({llm.get('detail')})")

    if (
        not config.DEV_MODE
        and config.GITHUB_APP_ID
        and not config.GITHUB_WEBHOOK_SECRET
    ):
        raise RuntimeError(
            "[orqis] GITHUB_WEBHOOK_SECRET is required when ORQIS_DEV_MODE=0 "
            "and GITHUB_APP_ID is set"
        )

    # Durable store: when DATABASE_URL is set, Postgres is the system of record.
    # Ensure the schema exists, then rehydrate Redis (the live/cache layer) from
    # Postgres so incidents, the audit trail, workspace settings, and the
    # PR->incident index survive a restart or a wiped Redis. Without DATABASE_URL
    # the backend runs purely on Redis exactly as before.
    from . import db, durable

    if durable.enabled():
        # If Postgres is momentarily unreachable at boot, degrade to Redis and
        # keep serving rather than crash-looping the whole backend. Durable
        # writes are already best-effort, so the system self-heals once the DB
        # is back and the next incident/change is written.
        try:
            await db.init_models()
            restored = await durable.rehydrate_redis()
            print(f"[orqis] durable store active — rehydrated {restored}", file=sys.stderr)
        except Exception as e:
            print(
                f"[orqis] WARNING: durable store bootstrap failed ({type(e).__name__}: {e}) "
                "— serving from Redis only until Postgres is reachable",
                file=sys.stderr,
            )

    # Safety net: reconcile any incidents stuck in pr_open whose merge webhook
    # was missed or misconfigured (U1/P4). Runs every 5 minutes.
    poll_task = asyncio.create_task(_poll_open_prs_loop())
    try:
        yield
    finally:
        poll_task.cancel()


async def _poll_open_prs_loop() -> None:
    from ..integrations.github import webhooks

    while True:
        try:
            await asyncio.sleep(300)
            await webhooks.poll_open_prs()
        except asyncio.CancelledError:
            break
        except Exception:
            # Never let the reconciler crash the server loop.
            pass


def _check_drain_auth(request: Request) -> None:
    """Enforce ORQIS_DRAIN_TOKEN when set. Accepts Authorization: Bearer <token> or ?token=."""
    if not config.DRAIN_TOKEN:
        return  # open in local dev
    # Check query param first (Railway log drain URLs support this)
    if request.query_params.get("token") == config.DRAIN_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:], config.DRAIN_TOKEN):
        return
    raise HTTPException(status_code=401, detail="invalid or missing drain token")


def _check_body_size(raw: bytes) -> None:
    if config.MAX_INGEST_BODY_BYTES and len(raw) > config.MAX_INGEST_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body too large")


def _check_admin_auth(request: Request) -> None:
    """
    Guard write paths with ORQIS_ADMIN_TOKEN (S2). Accepts the token via
    Authorization: Bearer <token> or X-Orqis-Admin-Token. Fail-closed when
    the token is unset — no dev-mode bypass.
    """
    if not config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="admin token not configured")
    header = request.headers.get("X-Orqis-Admin-Token", "")
    if header and hmac.compare_digest(header, config.ADMIN_TOKEN):
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and hmac.compare_digest(auth[7:], config.ADMIN_TOKEN):
        return
    raise HTTPException(status_code=401, detail="invalid or missing admin token")


def _has_admin_auth(request: Request) -> bool:
    """Return True when the request carries a valid admin token."""
    if not config.ADMIN_TOKEN:
        return False
    try:
        _check_admin_auth(request)
        return True
    except HTTPException:
        return False


app = FastAPI(title="Orqis", lifespan=lifespan)

# The dashboard runs on a different origin (localhost:3000 in dev, Vercel in
# prod) and hydrates over REST, so the browser needs CORS headers. Origins are
# configurable; defaults cover local dev. Set ORQIS_CORS_ORIGINS (comma list)
# or "*" to widen.
_cors_origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
_allow_credentials = config.MULTI_TENANT and "*" not in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HTTP endpoints -----------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ws_clients": ws_manager.manager.active_count,
        "multi_tenant": config.MULTI_TENANT,
    }


@app.get("/health/ready")
async def health_ready():
    from ..backend import health as health_mod

    return await health_mod.readiness()


# --- Auth (GitHub OAuth + workspace sessions) ---------------------------------

@app.get("/auth/github/login")
async def auth_github_login(invite: str = Query(default="")):
    if not config.GITHUB_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")
    state = secrets.token_urlsafe(24)
    r = await store.get_redis()
    payload = json.dumps({"invite": invite}) if invite else "1"
    await r.set(f"orqis:oauth:state:{state}", payload, ex=600)
    params = urlencode(
        {
            "client_id": config.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": f"{config.PUBLIC_URL.rstrip('/')}/auth/github/callback",
            "scope": "read:user",
            "state": state,
        }
    )
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{params}")


@app.get("/auth/github/callback")
async def auth_github_callback(
    request: Request,
    response: Response,
    code: str = "",
    state: str = "",
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")
    r = await store.get_redis()
    state_payload = await r.get(f"orqis:oauth:state:{state}")
    if not state_payload:
        raise HTTPException(status_code=403, detail="invalid oauth state")
    await r.delete(f"orqis:oauth:state:{state}")

    invite_token = ""
    if state_payload != "1":
        try:
            invite_token = json.loads(state_payload).get("invite") or ""
        except json.JSONDecodeError:
            pass

    async with httpx.AsyncClient(timeout=15.0) as http:
        token_resp = await http.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": config.GITHUB_OAUTH_CLIENT_ID,
                "client_secret": config.GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{config.PUBLIC_URL.rstrip('/')}/auth/github/callback",
            },
        )
        token_data = token_resp.json()
        access = token_data.get("access_token")
        if not access:
            raise HTTPException(status_code=403, detail="oauth token exchange failed")

        user_resp = await http.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access}",
                "Accept": "application/vnd.github+json",
            },
        )
        user = user_resp.json()

    github_id = user.get("id")
    login = user.get("login", "user")
    if not github_id:
        raise HTTPException(status_code=403, detail="invalid github user")

    if invite_token:
        try:
            workspace_id, _ws = await workspace_auth.accept_invite(
                invite_token,
                int(github_id),
                login,
                user.get("avatar_url", ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        workspace_id, _ws = await workspace_auth.get_or_create_user_workspace(
            github_id, login, user.get("avatar_url", "")
        )
    session_id = workspace_auth.create_session_id()
    await workspace_auth.save_session(
        session_id, workspace_id=workspace_id, github_id=github_id, login=login
    )

    # Ensure workspace has an ingest key
    keys = await workspace_auth.list_api_keys(workspace_id)
    if not keys:
        await workspace_auth.create_api_key(workspace_id, label="default")

    resp = RedirectResponse(url=f"{_dashboard_origin()}/dashboard")
    deps.set_session_cookie(resp, session_id)
    return resp


@app.get("/auth/me")
async def auth_me(request: Request):
    """Return auth state without requiring login (for AuthGuard)."""
    if not config.MULTI_TENANT:
        return {"authenticated": True, "multi_tenant": False, "workspace_id": "default"}
    session_id = deps._session_cookie(request)
    if not session_id:
        return {"authenticated": False, "multi_tenant": True}
    session = await workspace_auth.get_session(session_id)
    if not session:
        return {"authenticated": False, "multi_tenant": True}
    ws = await workspace_auth.get_workspace(session["workspace_id"])
    return {
        "authenticated": True,
        "login": session.get("login"),
        "workspace_id": session.get("workspace_id"),
        "workspace_name": ws.get("name") if ws else None,
        "multi_tenant": True,
    }


@app.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    session_id = deps._session_cookie(request)
    if session_id:
        await workspace_auth.delete_session(session_id)
    deps.clear_session_cookie(response)
    return {"ok": True}


@app.get("/auth/ws-ticket")
async def auth_ws_ticket(request: Request):
    wid = await deps.resolve_dashboard_workspace(request)
    return {"ticket": await deps.create_ws_ticket_async(wid)}


@app.get("/workspace/audit")
async def list_workspace_audit(request: Request, limit: int = 50):
    wid = await deps.resolve_dashboard_workspace(request)
    return await audit.list_recent(wid, limit=min(limit, 200))


@app.get("/workspace/api-keys")
async def list_workspace_api_keys(request: Request):
    wid = await deps.resolve_dashboard_workspace(request)
    return await workspace_auth.list_api_keys(wid)


@app.post("/workspace/api-keys")
async def create_workspace_api_key(request: Request, label: str = "default"):
    wid = await deps.resolve_dashboard_workspace(request)
    created = await workspace_auth.create_api_key(wid, label=label)
    await audit.record(
        "api_key.create",
        actor=deps.actor_from_request(request),
        resource_type="api_key",
        resource_id=created["meta"]["id"],
        ip=request.client.host if request.client else None,
    )
    return created


async def _require_workspace_owner(request: Request) -> tuple[str, dict]:
    wid = await deps.resolve_dashboard_workspace(request)
    session_id = deps._session_cookie(request)
    session = await workspace_auth.get_session(session_id or "")
    if not session:
        raise HTTPException(status_code=401, detail="not authenticated")
    role = await workspace_auth.get_member_role(wid, int(session["github_id"]))
    if role != "owner":
        raise HTTPException(status_code=403, detail="workspace owner required")
    return wid, session


@app.get("/invites/{token}/preview")
async def invite_preview(token: str):
    """Public metadata for an invite link (no auth)."""
    inv = await workspace_auth.get_invite(token)
    if not inv:
        raise HTTPException(status_code=404, detail="invite not found or expired")
    ws = await workspace_auth.get_workspace(inv["workspace_id"])
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    return {
        "workspace_name": ws.get("name"),
        "workspace_id": inv["workspace_id"],
        "role": inv.get("role", "member"),
        "created_by_login": inv.get("created_by_login"),
    }


@app.get("/workspace/members")
async def list_workspace_members(request: Request):
    wid = await deps.resolve_dashboard_workspace(request)
    return await workspace_auth.list_members(wid)


@app.get("/workspace/invites")
async def list_workspace_invites(request: Request):
    wid, _ = await _require_workspace_owner(request)
    return await workspace_auth.list_invites(wid)


@app.post("/workspace/invites")
async def create_workspace_invite(request: Request):
    wid, session = await _require_workspace_owner(request)
    inv = await workspace_auth.create_invite(
        wid,
        created_by_github_id=int(session["github_id"]),
        created_by_login=session.get("login", "owner"),
    )
    origin = _dashboard_origin()
    await audit.record(
        "invite.create",
        actor=deps.actor_from_request(request),
        resource_type="invite",
        resource_id=inv["token"],
        ip=request.client.host if request.client else None,
    )
    return {
        **inv,
        "url": f"{origin}/invite/{inv['token']}",
    }


@app.delete("/workspace/invites/{token}")
async def revoke_workspace_invite(request: Request, token: str):
    wid, _ = await _require_workspace_owner(request)
    ok = await workspace_auth.revoke_invite(wid, token)
    if not ok:
        raise HTTPException(status_code=404, detail="invite not found")
    await audit.record(
        "invite.revoke",
        actor=deps.actor_from_request(request),
        resource_type="invite",
        resource_id=token,
        ip=request.client.host if request.client else None,
    )
    return {"ok": True}


def _dashboard_origin() -> str:
    return config.CORS_ORIGINS.split(",")[0].strip() or "http://localhost:3000"


@app.delete("/workspace/api-keys/{key_id}")
async def revoke_workspace_api_key(request: Request, key_id: str):
    wid = await deps.resolve_dashboard_workspace(request)
    ok = await workspace_auth.revoke_api_key(wid, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="api key not found")
    await audit.record(
        "api_key.revoke",
        actor=deps.actor_from_request(request),
        resource_type="api_key",
        resource_id=key_id,
        ip=request.client.host if request.client else None,
    )
    return {"ok": True}


async def _ingest_lines(lines: list[str], source: str) -> dict:
    flat: list[str] = []
    for raw_line in lines:
        flat.extend(normalizer.normalize(str(raw_line).encode()))
    events = await log_reader.ingest_lines(flat or [str(x) for x in lines], source=source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast(
            "log.event", event.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
    return {"accepted": len(events)}


@app.post("/drain", status_code=202)
async def drain(
    request: Request,
    source: str = Query(default="unknown"),
):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        _check_drain_auth(request)
        await deps.bind_workspace("default")
    raw = await request.body()
    _check_body_size(raw)
    lines = normalizer.normalize(raw)
    if not lines:
        return {"accepted": 0}

    events = await log_reader.ingest_lines(lines, source=source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast(
            "log.event", event.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
    return {"accepted": len(events)}


@app.post("/ingest", status_code=202)
async def ingest(request: Request, body: IngestRequest):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")
    flat: list[str] = []
    for raw_line in body.lines:
        flat.extend(normalizer.normalize(raw_line.encode()))
    events = await log_reader.ingest_lines(flat or body.lines, source=body.source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast(
            "log.event", event.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
    return {"accepted": len(events)}


@app.post("/events", status_code=201)
async def receive_event(request: Request, event: LogEvent):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")
    import asyncio
    from ..rca.pipeline import _spawn, trigger

    await store.save_event(event)
    await ws_manager.manager.broadcast(
        "log.event", event.model_dump(mode="json"), workspace_id=get_workspace_id()
    )

    if event.is_error and 'File "' in event.raw_line:
        wid = get_workspace_id()
        _spawn(
            trigger(
                source_event_id=event.id,
                error_message=event.raw_line,
                error_type=event.error_type,
                source=event.source,
            ),
            workspace_id=wid,
        )

    return {"id": event.id}


@app.patch("/events/{event_id}/interpretation")
async def update_interpretation(request: Request, event_id: str, body: InterpretationUpdate):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")
    updated = await store.update_interpretation(event_id, body.interpretation)
    if updated is None:
        raise HTTPException(status_code=404, detail="event not found")

    await ws_manager.manager.broadcast(
        "log.interpretation",
        {"event_id": event_id, "interpretation": body.interpretation},
        workspace_id=get_workspace_id(),
    )
    return {"ok": True}


@app.get("/events", response_model=list[LogEvent])
async def get_events(request: Request, limit: int = 100):
    await deps.resolve_dashboard_workspace(request)
    return await store.get_recent_events(limit=min(limit, 500))


@app.post("/trace", status_code=201)
async def receive_trace(request: Request, event: TraceEvent):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")
    import asyncio
    from ..rca import anomaly
    from ..rca.pipeline import _spawn, trigger, trigger_anomaly

    await store.save_trace_event(event)
    await ws_manager.manager.broadcast(
        "trace.event", event.model_dump(mode="json"), workspace_id=get_workspace_id()
    )

    signal = await anomaly.observe(event)
    if signal is not None:
        _spawn(trigger_anomaly(signal), workspace_id=get_workspace_id())

    if event.is_error and event.error_message:
        from ..daemon.interpreter import fallback

        fb = fallback(event.error_type)
        await store.update_trace_interpretation(event.id, fb)
        await ws_manager.manager.broadcast(
            "trace.interpretation",
            {"event_id": event.id, "interpretation": fb},
            workspace_id=get_workspace_id(),
        )
        _spawn(
            _interpret_trace(event.id, event.error_message, event.error_type),
            workspace_id=get_workspace_id(),
        )

        if 'File "' in event.error_message:
            _spawn(
                trigger(
                    source_event_id=event.id,
                    error_message=event.error_message,
                    error_type=event.error_type,
                    source=event.source,
                ),
                workspace_id=get_workspace_id(),
            )

    return {"id": event.id, "circuit_break": anomaly.is_tripped(event.source)}


async def _interpret_trace(event_id: str, error_message: str, error_type) -> None:
    from ..daemon.interpreter import interpret
    text = await interpret(error_message, error_type)
    await store.update_trace_interpretation(event_id, text)
    await ws_manager.manager.broadcast(
        "trace.interpretation",
        {"event_id": event_id, "interpretation": text},
        workspace_id=get_workspace_id(),
    )


@app.get("/traces", response_model=list[TraceEvent])
async def get_traces(request: Request, limit: int = 100):
    await deps.resolve_dashboard_workspace(request)
    return await store.get_recent_traces(limit=min(limit, 500))


# --- RCA pipeline trigger ----------------------------------------------------

@app.post("/rca/trigger", status_code=202)
async def rca_trigger(request: Request, body: dict):
    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")
    from ..rca.pipeline import _spawn, trigger

    traceback_text: str = body.get("traceback", "")
    source: str = body.get("source", "unknown")

    if not traceback_text:
        return {"ok": False, "reason": "empty traceback"}

    from ..daemon.pattern_matcher import classify
    last_line = [l for l in traceback_text.splitlines() if l.strip()][-1]
    _, _, error_type, _, _ = classify(last_line)

    _spawn(
        trigger(
            source_event_id="traceback",
            error_message=traceback_text,
            error_type=error_type,
            source=source,
        ),
        workspace_id=get_workspace_id(),
    )
    return {"ok": True}


@app.post("/integrations/sentry/webhook", status_code=202)
async def sentry_webhook(request: Request):
    """
    Receive a Sentry error webhook, reconstruct the traceback from its
    structured stack frames, and run the same RCA pipeline used for raw logs.

    Multi-tenant: include the workspace ingest API key as
    ``Authorization: Bearer orqs_…`` (same key used for /ingest).

    Configure in Sentry: Settings -> Developer Settings -> New Internal
    Integration -> Webhook URL = https://your-backend/integrations/sentry/webhook
    Set ORQIS_SENTRY_SECRET to the integration's Client Secret to enforce
    signature verification.
    """
    from ..integrations import sentry
    from ..rca.pipeline import _spawn, trigger

    if config.MULTI_TENANT:
        await deps.resolve_ingest_workspace(request)
    else:
        await deps.bind_workspace("default")

    raw = await request.body()
    signature = request.headers.get("sentry-hook-signature")
    if not sentry.verify_signature(raw, signature, config.SENTRY_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="invalid sentry signature")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json payload")

    result = sentry.extract_traceback(payload)
    if result is None:
        return {"ok": False, "reason": "no actionable stacktrace in payload"}

    traceback_text, source = result

    from ..daemon.pattern_matcher import classify
    last_line = [l for l in traceback_text.splitlines() if l.strip()][-1]
    _, _, error_type, _, _ = classify(last_line)

    wid = get_workspace_id()
    _spawn(
        trigger(
            source_event_id="sentry",
            error_message=traceback_text,
            error_type=error_type,
            source=source,
        ),
        workspace_id=wid,
    )
    return {"ok": True}


# --- GitHub App integration ---------------------------------------------------

@app.get("/integrations/ide-setup")
async def ide_setup():
    """
    Return copy-paste MCP configuration snippets for common IDEs and agents.
    The protocol is the same everywhere: stdio JSON-RPC to `orqis mcp`.
    """
    backend = config.BACKEND_URL.rstrip("/")
    base_args = ["mcp", "--backend-url", backend]
    mcp_block = {
        "command": "orqis",
        "args": base_args,
        "env": {
            "ORQIS_API_KEY": "<workspace-api-key-from-settings>",
            "ORQIS_ADMIN_TOKEN": "<optional-local-dev-only>",
        },
    }
    return {
        "backend_url": backend,
        "mcp_command": "orqis mcp",
        "note": (
            "Same MCP server for every IDE — only the config file location differs. "
            "Paste the fix prompt from the dashboard into any AI chat if you do not use MCP."
        ),
        "configs": {
            "cursor_windsurf_claude_project": {"mcpServers": {"orqis": mcp_block}},
            "vscode_user_settings": {
                "mcp": {"servers": {"orqis": mcp_block}}
            },
            "stdio_only": {
                "command": "orqis",
                "args": base_args,
            },
        },
        "ides": [
            {"name": "Cursor", "config": "Project `.mcp.json` or Cursor Settings → MCP"},
            {"name": "Windsurf", "config": "Project `.mcp.json`"},
            {"name": "Claude Code", "config": "Project `.mcp.json` or `~/.claude/mcp.json`"},
            {"name": "VS Code", "config": "Settings → MCP → add server (see vscode_user_settings)"},
            {"name": "JetBrains / Zed / others", "config": "Add stdio MCP server pointing at `orqis mcp`"},
            {"name": "Any editor", "config": "Dashboard → Copy for AI assistant → paste into chat"},
        ],
    }


@app.get("/integrations/github/connect")
async def github_connect(request: Request):
    from ..integrations.github import auth as gh_auth
    from ..integrations.github import install_state

    wid = await deps.resolve_dashboard_workspace(request)
    settings = await store.get_settings()
    install_url = ""
    if config.GITHUB_APP_SLUG:
        state = install_state.create_state(wid)
        install_url = (
            f"https://github.com/apps/{config.GITHUB_APP_SLUG}/installations/new"
            f"?state={state}"
        )
    return {
        "configured": gh_auth.is_configured(),
        "install_url": install_url,
        "connected": bool(settings.get("installation_id")),
        "account_login": settings.get("account_login"),
        "repos": settings.get("repos", []),
    }


@app.get("/integrations/github/callback")
async def github_callback(
    request: Request,
    installation_id: int = 0,
    setup_action: str = "",
    state: str = "",
):
    """
    Post-install redirect target. GitHub sends installation_id + setup_action.
    Requires a valid signed `state` from the install URL (C1).
    """
    from ..integrations.github import auth as gh_auth
    from ..integrations.github import install_state

    if not install_state.verify_state(state):
        raise HTTPException(status_code=403, detail="invalid or expired install state")

    workspace_id = install_state.parse_state(state)
    if not workspace_id:
        raise HTTPException(status_code=403, detail="invalid install state payload")

    token = set_workspace_id(workspace_id)
    try:
        if installation_id:
            if gh_auth.is_configured():
                token_gh = await gh_auth.installation_token(installation_id)
                if token_gh is None:
                    raise HTTPException(
                        status_code=403,
                        detail="installation not accessible to this GitHub App",
                    )
            from ..integrations.github import sync as gh_sync

            await gh_sync.refresh_installation_repos(installation_id)
            await workspace_auth.set_install_workspace(installation_id, workspace_id)
            settings = await store.get_settings()
            connect = {
                "configured": bool(config.GITHUB_APP_ID and config.GITHUB_APP_SLUG),
                "install_url": "",
                "connected": bool(settings.get("installation_id")),
                "account_login": settings.get("account_login"),
                "repos": settings.get("repos", []),
            }
            await ws_manager.manager.broadcast(
                "settings.updated", connect, workspace_id=workspace_id
            )
    finally:
        reset_workspace_id(token)

    dashboard = _dashboard_origin()
    return RedirectResponse(url=f"{dashboard}/settings?github=connected")


@app.post("/integrations/github/webhook", status_code=202)
async def github_webhook(request: Request):
    """
    Receive GitHub App webhooks: installation changes and pull_request merges.
    Verifies the HMAC signature and dedups deliveries before dispatching.
    """
    from ..integrations.github import webhooks

    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not webhooks.verify_signature(raw, signature, config.GITHUB_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="invalid github signature")

    delivery = request.headers.get("X-GitHub-Delivery", "")
    if await store.delivery_seen(delivery):
        return {"ok": True, "duplicate": True}

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json payload")

    result = await webhooks.handle(event, payload)
    return result


@app.post("/integrations/github/refresh-repos")
async def github_refresh_repos(request: Request):
    await deps.resolve_write_auth(request)
    from ..integrations.github import auth as gh_auth
    from ..integrations.github import sync as gh_sync

    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    updated = await gh_sync.refresh_installation_repos(installation_id)
    connect = {
        "configured": gh_auth.is_configured(),
        "install_url": "",
        "connected": bool(updated.get("installation_id")),
        "account_login": updated.get("account_login"),
        "repos": updated.get("repos", []),
    }
    await ws_manager.manager.broadcast(
        "settings.updated", connect, workspace_id=get_workspace_id()
    )
    return connect


@app.get("/integrations/github/setup-status")
async def github_setup_status(request: Request):
    await deps.resolve_dashboard_workspace(request)
    from ..integrations.github import app_register, auth as gh_auth

    settings = await store.get_settings()
    webhook_ok = bool(config.GITHUB_WEBHOOK_SECRET) or config.DEV_MODE
    base = config.PUBLIC_URL.rstrip("/")
    install_url = ""
    if config.GITHUB_APP_SLUG:
        from ..integrations.github import install_state

        wid = get_workspace_id()
        state = install_state.create_state(wid)
        install_url = (
            f"https://github.com/apps/{config.GITHUB_APP_SLUG}/installations/new"
            f"?state={state}"
        )
    return {
        "app_configured": gh_auth.is_configured(),
        "registration_allowed": app_register.registration_allowed(),
        "connected": bool(settings.get("installation_id")),
        "webhook_configured": webhook_ok,
        "webhook_url": f"{base}/integrations/github/webhook",
        "repos_count": len(settings.get("repos") or []),
        "public_url": config.PUBLIC_URL,
        "app_slug": config.GITHUB_APP_SLUG or None,
        "install_url": install_url,
        "register_status": app_register.read_status(),
    }


@app.post("/integrations/github/register/start")
async def github_register_start(request: Request):
    """Start in-product GitHub App manifest registration (local/self-hosted)."""
    await deps.resolve_write_auth(request)
    from ..integrations.github import app_register

    if not app_register.registration_allowed():
        raise HTTPException(
            status_code=409,
            detail="GitHub App already configured or registration disabled in hosted mode",
        )
    manifest = app_register.build_manifest()
    url = app_register.register_url(manifest)
    app_register.STATUS_PATH.parent.mkdir(exist_ok=True)
    app_register.STATUS_PATH.write_text(
        json.dumps({"state": "waiting", "register_url": url}, indent=2),
        encoding="utf-8",
    )
    return {"register_url": url, "webhook_will_activate": app_register._webhook_active()}


@app.get("/integrations/github/register/callback")
async def github_register_callback(code: str = "", state: str = ""):
    """GitHub manifest redirect — exchange code for app credentials."""
    from ..integrations.github import app_register

    if not code:
        raise HTTPException(status_code=400, detail="missing manifest code")
    try:
        data = await app_register.convert_manifest(code)
        status = app_register.apply_runtime_credentials(data)
    except Exception as exc:
        app_register.STATUS_PATH.parent.mkdir(exist_ok=True)
        app_register.STATUS_PATH.write_text(
            json.dumps({"state": "error", "error": str(exc)}), encoding="utf-8"
        )
        raise HTTPException(status_code=502, detail=f"manifest conversion failed: {exc}") from exc

    dashboard = _dashboard_origin()
    return RedirectResponse(url=f"{dashboard}/settings?github=app_registered")


# --- Workspace sources / stats / notifications ---------------------------------

@app.get("/workspace/sources")
async def workspace_sources(request: Request, limit: int = Query(default=50, le=100)):
    await deps.resolve_dashboard_workspace(request)
    from ..backend import sources as sources_mod

    return {"sources": await sources_mod.recent_sources(limit)}


@app.get("/incidents/stats")
async def incidents_stats(request: Request):
    await deps.resolve_dashboard_workspace(request)
    from ..backend import stats as stats_mod

    return await stats_mod.incident_stats()


@app.post("/workspace/notifications/test")
async def notifications_test(request: Request):
    await deps.resolve_write_auth(request)
    from ..notifications import dispatcher

    ok = await dispatcher.send_test()
    if not ok:
        raise HTTPException(status_code=400, detail="no notification URLs configured")
    return {"ok": True}


# --- Third-party ingest adapters ----------------------------------------------

@app.post("/ingest/datadog")
async def ingest_datadog(request: Request):
    await deps.resolve_ingest_workspace(request)
    from ..ingest import adapters

    body = await request.json()
    lines, source = adapters.from_datadog(body)
    return await _ingest_lines(lines, source)


@app.post("/ingest/cloudwatch")
async def ingest_cloudwatch(request: Request):
    await deps.resolve_ingest_workspace(request)
    from ..ingest import adapters

    body = await request.json()
    lines, source = adapters.from_cloudwatch(body)
    return await _ingest_lines(lines, source)


@app.post("/ingest/otel")
async def ingest_otel(request: Request):
    await deps.resolve_ingest_workspace(request)
    from ..ingest import adapters

    body = await request.json()
    lines, source = adapters.from_otel(body)
    return await _ingest_lines(lines, source)


# --- Workspace settings -------------------------------------------------------

_SECRET_SETTING_KEYS = {"cursor_api_key"}  # never echoed back


@app.get("/settings")
async def get_settings_route(request: Request):
    await deps.resolve_dashboard_workspace(request)
    settings = await store.get_settings()
    return {k: v for k, v in settings.items() if k not in _SECRET_SETTING_KEYS}


@app.put("/settings")
async def update_settings(request: Request):
    await deps.resolve_write_auth(request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="settings body must be an object")

    url = body.get("hot_reload_webhook_url")
    if url:
        from ..integrations.github import pr_service

        if not pr_service._safe_callback_url(url):
            raise HTTPException(
                status_code=400,
                detail="hot_reload_webhook_url must be HTTPS and not an internal address",
            )

    for notify_key in ("notification_webhook_url", "notification_slack_url"):
        notify_url = body.get(notify_key)
        if notify_url:
            from ..integrations.github import pr_service

            if not pr_service._safe_callback_url(notify_url):
                raise HTTPException(
                    status_code=400,
                    detail=f"{notify_key} must be HTTPS and not an internal address",
                )

    # A user can only map/select repos their installation actually granted.
    current = await store.get_settings()
    granted = set(current.get("repos") or [])
    if granted:
        repo_map = body.get("source_repo_map")
        if isinstance(repo_map, dict):
            bad = sorted({r for r in repo_map.values() if r and r not in granted})
            if bad:
                raise HTTPException(
                    status_code=400,
                    detail=f"not in your connected repositories: {', '.join(bad)}",
                )
        default_repo = body.get("default_repo")
        if default_repo and default_repo not in granted:
            raise HTTPException(
                status_code=400,
                detail=f"default repository '{default_repo}' is not one you have access to",
            )

    updated = await store.save_settings(body)
    await audit.record(
        "settings.update",
        actor=deps.actor_from_request(request),
        resource_type="settings",
        resource_id=get_workspace_id(),
        ip=request.client.host if request.client else None,
    )
    return {k: v for k, v in updated.items() if k not in _SECRET_SETTING_KEYS}


@app.post("/demo/reset")
async def demo_reset(request: Request, clear: bool = False):
    if config.MULTI_TENANT:
        await deps.resolve_write_auth(request)
    else:
        await deps.bind_workspace("default")
    from ..rca import anomaly

    anomaly.reset()

    if clear:
        counts = await store.clear_all()
        await ws_manager.manager.broadcast("store.cleared", {}, workspace_id=get_workspace_id())
        return {"ok": True, "cleared": counts}

    return {"ok": True}


# --- Incidents ----------------------------------------------------------------

@app.get("/incidents", response_model=list[Incident])
async def get_incidents(request: Request, limit: int = 50):
    await deps.resolve_dashboard_workspace(request)
    return await store.get_recent_incidents(limit=min(limit, 200))


@app.get("/changes", response_model=list[ChangeLogEntry])
async def get_changes(request: Request, limit: int = 100):
    await deps.resolve_dashboard_workspace(request)
    entries = await store.get_recent_changes(limit=min(limit, 200))
    if config.MULTI_TENANT or _has_admin_auth(request):
        return entries
    return [e.model_copy(update={"diff": None}) for e in entries]


@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(request: Request, incident_id: str):
    await deps.resolve_dashboard_workspace(request)
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/incidents/{incident_id}/approve")
async def approve_incident(request: Request, incident_id: str, force: bool = False):
    await deps.resolve_write_auth(request)
    if config.HOSTED:
        raise HTTPException(
            status_code=409,
            detail="local disk apply is disabled in hosted mode — merge the GitHub PR",
        )
    if force and config.CI_MODE and not config.ALLOW_FORCE:
        raise HTTPException(
            status_code=403,
            detail="force=true is blocked in CI — set ORQIS_ALLOW_FORCE=1 to override",
        )
    from ..rca.applier import apply

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    # GitHub PR-first: never write to disk for a repo-mapped incident (U3).
    if incident.repo_full_name:
        detail = "incident is delivered as a GitHub PR — review and merge it there"
        if incident.pr_url:
            detail += f": {incident.pr_url}"
        raise HTTPException(status_code=409, detail=detail)

    allowed = (IncidentStatus.PATCHED,)
    if force:
        allowed = (IncidentStatus.PATCHED, IncidentStatus.LOW_CONFIDENCE)
    if incident.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"incident is {incident.status.value}, not patched "
                f"— pass ?force=true to override low-confidence block"
            ),
        )
    if not incident.diff:
        raise HTTPException(status_code=409, detail="no diff available to apply")

    # Use the configured project root, captured at startup, so a changed backend
    # cwd can't misdirect the patch.
    success, reason = apply(incident.diff, config.PROJECT_ROOT)

    if not success:
        raise HTTPException(status_code=422, detail=f"patch failed: {reason}")

    updated = await store.update_incident(
        incident_id, status=IncidentStatus.APPROVED.value
    )
    await audit.record(
        "incident.approve",
        actor=deps.actor_from_request(request),
        resource_type="incident",
        resource_id=incident_id,
        ip=request.client.host if request.client else None,
    )
    await ws_manager.manager.broadcast(
        "incident.approved", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
    )
    from . import changelog

    short = (updated.repo_relative_path or updated.file_path or "the file")
    await changelog.record(
        "fix_applied",
        updated,
        f"Applied fix to {short.replace(chr(92), '/').split('/')[-1]}",
        applied_locally=True,
        local_path=incident.file_path,
    )
    return {"ok": True, "file": incident.file_path}


@app.post("/incidents/{incident_id}/dismiss")
async def dismiss_incident(request: Request, incident_id: str):
    await deps.resolve_write_auth(request)
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    # Close any open PR on GitHub before dismissing.
    if incident.pr_number and incident.repo_full_name:
        from ..integrations.github import pr_service

        await pr_service.close_pr_for_incident(incident)

    updated = await store.update_incident(
        incident_id, status=IncidentStatus.DISMISSED.value
    )
    # Re-arm the rolling TTL now that the incident is terminal (P1).
    await store.set_incident_ttl(incident_id)
    await audit.record(
        "incident.dismiss",
        actor=deps.actor_from_request(request),
        resource_type="incident",
        resource_id=incident_id,
        ip=request.client.host if request.client else None,
    )
    await ws_manager.manager.broadcast(
        "incident.dismissed", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
    )
    from . import changelog

    await changelog.record("dismissed", updated, "Dismissed — no change made")
    return {"ok": True}


@app.post("/incidents/{incident_id}/open-pr")
async def open_pr(request: Request, incident_id: str):
    await deps.resolve_write_auth(request)
    from ..integrations.github import auth as gh_auth
    from ..integrations.github import pr_service

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if not gh_auth.is_configured():
        raise HTTPException(status_code=409, detail="GitHub App is not configured")
    if not incident.repo_full_name:
        raise HTTPException(
            status_code=409,
            detail="incident has no mapped repo — map source -> repo in Settings",
        )
    if not incident.diff:
        raise HTTPException(status_code=409, detail="no diff available to open a PR")

    from ..rca.pipeline import _spawn

    wid = get_workspace_id()
    _spawn(pr_service.open_fix_pr(incident), workspace_id=wid)
    await audit.record(
        "incident.open_pr",
        actor=deps.actor_from_request(request),
        resource_type="incident",
        resource_id=incident_id,
        ip=request.client.host if request.client else None,
    )
    return {"ok": True, "status": "opening"}


@app.post("/incidents/{incident_id}/resolve")
async def resolve_incident(request: Request, incident_id: str):
    await deps.resolve_write_auth(request)
    from ..integrations.github import pr_service

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    if incident.pr_number and incident.repo_full_name:
        await pr_service.mark_resolved(incident_id, incident.repo_full_name, incident.pr_number)
    else:
        updated = await store.update_incident(
            incident_id, status=IncidentStatus.RESOLVED.value
        )
        await store.set_incident_ttl(incident_id)
        await ws_manager.manager.broadcast(
            "incident.resolved", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
        from . import changelog

        await changelog.record("resolved", updated, "Marked resolved")
    await audit.record(
        "incident.resolve",
        actor=deps.actor_from_request(request),
        resource_type="incident",
        resource_id=incident_id,
        ip=request.client.host if request.client else None,
    )
    return {"ok": True}


@app.get("/incidents/{incident_id}/prompt")
async def get_incident_prompt(request: Request, incident_id: str):
    await deps.resolve_dashboard_workspace(request)
    from ..rca.ide_prompt import build_fix_prompt

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    return {"prompt": build_fix_prompt(incident)}


# --- WebSocket ----------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, ticket: str = Query(default="")):
    from starlette.websockets import WebSocketDisconnect as WSD

    fake_request = Request({"type": "http", "headers": []})
    # Cookie header for session auth on WS handshake
    cookie_header = ws.headers.get("cookie", "")
    if cookie_header:
        fake_request = Request(
            {
                "type": "http",
                "headers": [(b"cookie", cookie_header.encode())],
            }
        )
    tok = None
    try:
        wid = await deps.resolve_ws_workspace(fake_request, ticket=ticket)
    except HTTPException:
        await ws.close(code=4401)
        return

    await ws_manager.manager.connect(ws, workspace_id=wid)
    tok = set_workspace_id(wid)
    try:
        events = await store.get_recent_events(limit=200)
        for event in events:
            await ws.send_json(
                {"type": "log.event", "data": event.model_dump(mode="json")}
            )
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, WSD):
        ws_manager.manager.disconnect(ws)
    finally:
        if tok is not None:
            reset_workspace_id(tok)
