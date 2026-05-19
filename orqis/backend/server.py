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

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from .. import config
from ..backend import store, ws_manager
from ..backend.models import Incident, IncidentStatus, IngestRequest, InterpretationUpdate, LogEvent, TraceEvent
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
    yield


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


app = FastAPI(title="Orqis", lifespan=lifespan)


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
    await store.save_trace_event(event)
    await ws_manager.manager.broadcast("trace.event", event.model_dump(mode="json"))

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
        import asyncio
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

    return {"id": event.id}


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


# --- Incidents ----------------------------------------------------------------

@app.get("/incidents", response_model=list[Incident])
async def get_incidents(limit: int = 50):
    """Return recent incidents ordered oldest-first (for the dashboard timeline)."""
    return await store.get_recent_incidents(limit=min(limit, 200))


@app.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.post("/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str):
    """
    Apply the generated patch to disk and mark the incident as approved.
    This is the only endpoint that writes to the filesystem.
    Requires the incident to be in PATCHED status with a valid diff.
    """
    import os
    from ..rca.applier import apply

    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if incident.status != IncidentStatus.PATCHED:
        raise HTTPException(
            status_code=409,
            detail=f"incident is {incident.status.value}, not patched — cannot approve",
        )
    if not incident.diff:
        raise HTTPException(status_code=409, detail="no diff available to apply")

    project_root = os.getcwd()
    success, reason = apply(incident.diff, project_root)

    if not success:
        raise HTTPException(status_code=422, detail=f"patch failed: {reason}")

    updated = await store.update_incident(
        incident_id, status=IncidentStatus.APPROVED.value
    )
    await ws_manager.manager.broadcast(
        "incident.approved", updated.model_dump(mode="json")
    )
    return {"ok": True, "file": incident.file_path}


@app.post("/incidents/{incident_id}/dismiss")
async def dismiss_incident(incident_id: str):
    """Mark the incident as dismissed — no patch applied."""
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    updated = await store.update_incident(
        incident_id, status=IncidentStatus.DISMISSED.value
    )
    await ws_manager.manager.broadcast(
        "incident.dismissed", updated.model_dump(mode="json")
    )
    return {"ok": True}


@app.get("/incidents/{incident_id}/prompt")
async def get_incident_prompt(incident_id: str):
    """
    Return a ready-to-paste prompt for any AI coding assistant (Cursor, Claude Code, etc.).
    The frontend team can render this as a copy button on the incident card.
    """
    incident = await store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    lines = [
        "Orqis detected a production error in your codebase.",
        "",
        f"Error: {incident.error_message}",
    ]
    if incident.interpretation:
        lines.append(f"Plain English: {incident.interpretation}")
    if incident.file_path and incident.error_line:
        lines.append(f"Location: {incident.file_path}:{incident.error_line}")
    if incident.function_name:
        lines.append(f"Function: {incident.function_name}")
    if incident.code_context:
        lines.append(f"\nCode context (line {incident.context_start_line}):")
        lines.append(f"```python\n{incident.code_context}\n```")
    if incident.diff:
        lines.append("\nOrqis suggested fix (unified diff):")
        lines.append(f"```diff\n{incident.diff}\n```")
        lines.append("\nPlease review and apply this fix if it looks correct.")
    else:
        lines.append("\nNo automated fix was generated. Please investigate and fix manually.")

    return {"prompt": "\n".join(lines)}


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
