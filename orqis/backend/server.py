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
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .. import config
from ..backend import store, ws_manager
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

    if (
        not config.DEV_MODE
        and config.GITHUB_APP_ID
        and not config.GITHUB_WEBHOOK_SECRET
    ):
        raise RuntimeError(
            "[orqis] GITHUB_WEBHOOK_SECRET is required when ORQIS_DEV_MODE=0 "
            "and GITHUB_APP_ID is set"
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
    if auth.startswith("Bearer ") and auth[7:] == config.DRAIN_TOKEN:
        return
    raise HTTPException(status_code=401, detail="invalid or missing drain token")


def _check_admin_auth(request: Request) -> None:
    """
    Guard settings mutations with ORQIS_ADMIN_TOKEN (S2). Accepts the token via
    Authorization: Bearer <token> or X-Orqis-Admin-Token. Open in local dev when
    the token is unset.
    """
    if not config.ADMIN_TOKEN:
        return
    header = request.headers.get("X-Orqis-Admin-Token", "")
    if header == config.ADMIN_TOKEN:
        return
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:] == config.ADMIN_TOKEN:
        return
    raise HTTPException(status_code=401, detail="invalid or missing admin token")


def _has_admin_auth(request: Request) -> bool:
    """Return True when the request carries a valid admin token."""
    if not config.ADMIN_TOKEN:
        return config.DEV_MODE
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HTTP endpoints -----------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "ws_clients": ws_manager.manager.active_count}


@app.post("/drain", status_code=202)
async def drain(
    request: Request,
    source: str = Query(default="unknown"),
):
    """
    Universal log drain endpoint — accepts any format, any content-type.

    Supports: NDJSON, JSON array, single JSON object, plain text, logfmt,
    syslog, Docker JSON, Railway drain, Vercel log drain, Fly.io, custom.

    Usage:
      Railway: Settings -> Log Drains -> HTTP -> https://your-backend/drain?source=my-app
      Docker:  --log-driver=gelf  or  pipe stdout -> curl
      Manual:  curl -X POST .../drain?source=api --data-binary @/var/log/app.log
    """
    _check_drain_auth(request)
    raw = await request.body()
    lines = normalizer.normalize(raw)
    if not lines:
        return {"accepted": 0}

    events = await log_reader.ingest_lines(lines, source=source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast("log.event", event.model_dump(mode="json"))
    return {"accepted": len(events)}


@app.post("/ingest", status_code=202)
async def ingest(body: IngestRequest):
    """
    Structured batch ingest — JSON body with a lines array and source label.
    Each line is run through the normalizer so mixed formats in the array work.
    """
    # Normalize each line individually so any embedded JSON objects are flattened
    flat: list[str] = []
    for raw_line in body.lines:
        flat.extend(normalizer.normalize(raw_line.encode()))
    events = await log_reader.ingest_lines(flat or body.lines, source=body.source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast("log.event", event.model_dump(mode="json"))
    return {"accepted": len(events)}


@app.post("/events", status_code=201)
async def receive_event(event: LogEvent):
    """
    Accept a single classified LogEvent from the local daemon.
    Triggers the RCA pipeline for error events that contain a traceback.
    """
    import asyncio
    await store.save_event(event)
    await ws_manager.manager.broadcast("log.event", event.model_dump(mode="json"))

    # Trigger RCA only when the line contains a traceback file reference
    if event.is_error and 'File "' in event.raw_line:
        from ..rca.pipeline import trigger
        asyncio.create_task(trigger(
            source_event_id=event.id,
            error_message=event.raw_line,
            error_type=event.error_type,
            source=event.source,
        ))

    return {"id": event.id}


@app.patch("/events/{event_id}/interpretation")
async def update_interpretation(event_id: str, body: InterpretationUpdate):
    """
    Called by the daemon after the async LLM interpretation resolves.
    Updates the stored event and pushes a targeted update to the dashboard.
    """
    updated = await store.update_interpretation(event_id, body.interpretation)
    if updated is None:
        raise HTTPException(status_code=404, detail="event not found")

    await ws_manager.manager.broadcast(
        "log.interpretation",
        {"event_id": event_id, "interpretation": body.interpretation},
    )
    return {"ok": True}


@app.get("/events", response_model=list[LogEvent])
async def get_events(limit: int = 100):
    """Return the N most recent events for dashboard initial load."""
    return await store.get_recent_events(limit=min(limit, 500))


@app.post("/trace", status_code=201)
async def receive_trace(event: TraceEvent):
    """
    Accept a single TraceEvent from the SDK instrumentation layer.
    Stores it, broadcasts to dashboard, and fires async LLM interpretation
    for error events.
    """
    import asyncio

    from ..rca import anomaly

    await store.save_trace_event(event)
    await ws_manager.manager.broadcast("trace.event", event.model_dump(mode="json"))

    # Behavioural detection: watch the live stream for a runaway tool loop.
    # This fires no exception — it is only visible here, in the stream itself.
    signal = await anomaly.observe(event)
    if signal is not None:
        from ..rca.pipeline import trigger_anomaly
        asyncio.create_task(trigger_anomaly(signal))

    if event.is_error and event.error_message:
        from ..daemon.interpreter import fallback

        # Set fallback immediately so dashboard always has something readable
        fb = fallback(event.error_type)
        await store.update_trace_interpretation(event.id, fb)
        await ws_manager.manager.broadcast(
            "trace.interpretation",
            {"event_id": event.id, "interpretation": fb},
        )

        # Fire async LLM interpretation
        asyncio.create_task(_interpret_trace(event.id, event.error_message, event.error_type))

        # Trigger RCA pipeline if the error message contains a traceback
        if 'File "' in event.error_message:
            from ..rca.pipeline import trigger
            asyncio.create_task(trigger(
                source_event_id=event.id,
                error_message=event.error_message,
                error_type=event.error_type,
                source=event.source,
            ))

    # circuit_break tells the calling agent to stop: Orqis has confirmed a
    # runaway loop on this source. This is the closed-loop kill switch.
    return {"id": event.id, "circuit_break": anomaly.is_tripped(event.source)}


async def _interpret_trace(event_id: str, error_message: str, error_type) -> None:
    from ..daemon.interpreter import interpret
    text = await interpret(error_message, error_type)
    await store.update_trace_interpretation(event_id, text)
    await ws_manager.manager.broadcast(
        "trace.interpretation",
        {"event_id": event_id, "interpretation": text},
    )


@app.get("/traces", response_model=list[TraceEvent])
async def get_traces(limit: int = 100):
    """Return the N most recent trace events for dashboard initial load."""
    return await store.get_recent_traces(limit=min(limit, 500))


# --- RCA pipeline trigger ----------------------------------------------------

@app.post("/rca/trigger", status_code=202)
async def rca_trigger(body: dict):
    """
    Accept a full multi-line traceback from the daemon and run the RCA pipeline.
    Called automatically when the daemon detects a complete Python traceback.
    """
    import asyncio
    from ..rca.pipeline import trigger

    traceback_text: str = body.get("traceback", "")
    source: str = body.get("source", "unknown")

    if not traceback_text:
        return {"ok": False, "reason": "empty traceback"}

    # Classify the error type from the traceback terminal line
    from ..daemon.pattern_matcher import classify
    last_line = [l for l in traceback_text.splitlines() if l.strip()][-1]
    _, _, error_type, _, _ = classify(last_line)

    asyncio.create_task(trigger(
        source_event_id="traceback",
        error_message=traceback_text,
        error_type=error_type,
        source=source,
    ))
    return {"ok": True}


@app.post("/integrations/sentry/webhook", status_code=202)
async def sentry_webhook(request: Request):
    """
    Receive a Sentry error webhook, reconstruct the traceback from its
    structured stack frames, and run the same RCA pipeline used for raw logs.

    Configure in Sentry: Settings -> Developer Settings -> New Internal
    Integration -> Webhook URL = https://your-backend/integrations/sentry/webhook
    Set ORQIS_SENTRY_SECRET to the integration's Client Secret to enforce
    signature verification.
    """
    import asyncio

    from ..integrations import sentry
    from ..rca.pipeline import trigger

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

    asyncio.create_task(trigger(
        source_event_id="sentry",
        error_message=traceback_text,
        error_type=error_type,
        source=source,
    ))
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
        "env": {"ORQIS_ADMIN_TOKEN": "<optional-if-set-on-backend>"},
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
async def github_connect():
    """
    Return the GitHub App install URL + current connection state for the
    Settings page. The user clicks install_url, picks repos on GitHub, and the
    `installation` webhook (and the callback below) records the installation.
    """
    from ..integrations.github import install_state

    settings = await store.get_settings()
    install_url = ""
    if config.GITHUB_APP_SLUG:
        state = install_state.create_state()
        install_url = (
            f"https://github.com/apps/{config.GITHUB_APP_SLUG}/installations/new"
            f"?state={state}"
        )
    return {
        "configured": bool(config.GITHUB_APP_ID and config.GITHUB_APP_SLUG),
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

    if installation_id:
        if gh_auth.is_configured():
            token = await gh_auth.installation_token(installation_id)
            if token is None:
                raise HTTPException(
                    status_code=403,
                    detail="installation not accessible to this GitHub App",
                )
        repos = await gh_auth.list_installation_repos(installation_id)
        await store.save_settings({"installation_id": installation_id, "repos": repos})
        connect = await github_connect()
        await ws_manager.manager.broadcast("settings.updated", connect)

    dashboard = config.CORS_ORIGINS.split(",")[0].strip() or "http://localhost:3000"
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


# --- Workspace settings -------------------------------------------------------

_SECRET_SETTING_KEYS = {"cursor_api_key"}  # never echoed back


@app.get("/settings")
async def get_settings():
    """
    Return workspace settings for the dashboard. Secret-bearing fields are never
    included in the response.
    """
    settings = await store.get_settings()
    return {k: v for k, v in settings.items() if k not in _SECRET_SETTING_KEYS}


@app.put("/settings")
async def update_settings(request: Request):
    """
    Update workspace settings (source->repo map, toggles, hot-reload URL).
    Guarded by ORQIS_ADMIN_TOKEN (S2). Validates the hot-reload URL is HTTPS and
    not an internal address before storing.
    """
    _check_admin_auth(request)
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

    updated = await store.save_settings(body)
    return {k: v for k, v in updated.items() if k not in _SECRET_SETTING_KEYS}


@app.post("/demo/reset")
async def demo_reset(clear: bool = False):
    """
    Reset the runaway-loop demo so it can be run again.

    Clears the anomaly detector's in-memory state so the circuit breaker
    re-trips on the next run. The incident dedup table is intentionally NOT
    cleared: that lets repeated runs of the same loop collapse into one
    incident (bumping its hit count) instead of spawning a duplicate each time.

    Pass ?clear=true to also delete all stored incidents and tell the dashboard
    to empty its list — used once to wipe accumulated demo runs.
    """
    from ..rca import anomaly

    anomaly.reset()

    if clear:
        counts = await store.clear_all()
        await ws_manager.manager.broadcast("store.cleared", {})
        return {"ok": True, "cleared": counts}

    return {"ok": True}


# --- Incidents ----------------------------------------------------------------

@app.get("/incidents", response_model=list[Incident])
async def get_incidents(limit: int = 50):
    """Return recent incidents ordered oldest-first (for the dashboard timeline)."""
    return await store.get_recent_incidents(limit=min(limit, 200))


@app.get("/changes", response_model=list[ChangeLogEntry])
async def get_changes(request: Request, limit: int = 100):
    """Return the change log. Full diffs require admin auth (H6)."""
    entries = await store.get_recent_changes(limit=min(limit, 200))
    if _has_admin_auth(request):
        return entries
    return [e.model_copy(update={"diff": None}) for e in entries]


@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/incidents/{incident_id}/approve")
async def approve_incident(request: Request, incident_id: str, force: bool = False):
    """
    Apply the generated patch to disk and mark the incident as approved.
    This is the only endpoint that writes to the filesystem.

    Normally requires PATCHED status. LOW_CONFIDENCE incidents are blocked
    unless ?force=true is set — a human is signing off on a risky patch.

    For GitHub-connected incidents this local-disk path is disabled: the fix is
    delivered as a reviewable PR instead (merge it on GitHub).
    """
    _check_admin_auth(request)
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
    await ws_manager.manager.broadcast(
        "incident.approved", updated.model_dump(mode="json")
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
    """
    Mark the incident as dismissed — no patch applied. If a fix PR was opened,
    close it and clean up its branch (G4/O2).
    """
    _check_admin_auth(request)
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
    await ws_manager.manager.broadcast(
        "incident.dismissed", updated.model_dump(mode="json")
    )
    from . import changelog

    await changelog.record("dismissed", updated, "Dismissed — no change made")
    return {"ok": True}


@app.post("/incidents/{incident_id}/open-pr")
async def open_pr(request: Request, incident_id: str):
    """
    Manually open (or retry) a fix PR for an incident — used for the dashboard
    "Open PR" action on low-confidence incidents and the retry button on
    pr_failed / patch_stale.
    """
    _check_admin_auth(request)
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

    asyncio.create_task(pr_service.open_fix_pr(incident))
    return {"ok": True, "status": "opening"}


@app.post("/incidents/{incident_id}/resolve")
async def resolve_incident(request: Request, incident_id: str):
    """
    Manual "Mark resolved" override for when a PR was merged but the webhook was
    missed (U1).
    """
    _check_admin_auth(request)
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
            "incident.resolved", updated.model_dump(mode="json")
        )
        from . import changelog

        await changelog.record("resolved", updated, "Marked resolved")
    return {"ok": True}


@app.get("/incidents/{incident_id}/prompt")
async def get_incident_prompt(incident_id: str):
    """
    Return a ready-to-paste prompt for any AI coding assistant in any IDE.
    """
    from ..rca.ide_prompt import build_fix_prompt

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    return {"prompt": build_fix_prompt(incident)}


# --- WebSocket ----------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.manager.connect(ws)
    try:
        # Send recent event history on connect so the dashboard can hydrate
        events = await store.get_recent_events(limit=200)
        for event in events:
            await ws.send_json(
                {"type": "log.event", "data": event.model_dump(mode="json")}
            )
        # Keep the connection alive — wait for client disconnect
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.manager.disconnect(ws)
