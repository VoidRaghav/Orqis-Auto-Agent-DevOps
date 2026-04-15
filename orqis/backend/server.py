"""
Orqis backend server.

Endpoints:
  POST /ingest              - Accept a batch of raw log lines (HTTP push from daemon or CI)
  POST /events              - Accept a single classified LogEvent (from the daemon)
  PATCH /events/{id}/interpretation  - Update interpretation after LLM resolves
  GET  /events              - Fetch recent events (dashboard initial load)
  WS   /ws                  - WebSocket for real-time dashboard updates
  GET  /health              - Health check
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from ..backend import store, ws_manager
from ..backend.models import IngestRequest, InterpretationUpdate, LogEvent
from ..daemon import log_reader


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up Redis connection on startup
    await store.get_redis()
    yield


app = FastAPI(title="Orqis", lifespan=lifespan)


# --- HTTP endpoints -----------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "ws_clients": ws_manager.manager.active_count}


@app.post("/ingest", status_code=202)
async def ingest(body: IngestRequest):
    """
    Accept raw log lines from a server (HTTP push mode).
    Classifies each line, stores it, and broadcasts to the dashboard.
    LLM interpretation fires async for error lines.
    """
    events = await log_reader.ingest_lines(body.lines, source=body.source)
    for event in events:
        await store.save_event(event)
        await ws_manager.manager.broadcast("log.event", event.model_dump(mode="json"))
    return {"accepted": len(events)}


@app.post("/events", status_code=201)
async def receive_event(event: LogEvent):
    """
    Accept a single classified LogEvent from the local daemon.
    Used when the daemon runs as a sidecar (stdin/file tail mode).
    """
    await store.save_event(event)
    await ws_manager.manager.broadcast("log.event", event.model_dump(mode="json"))
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
