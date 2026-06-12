"""
Redis-backed event store.

Each LogEvent is stored as a JSON hash at key orqis:event:<id>.
A sorted set orqis:events:timeline (score = unix timestamp) provides
ordered access for the dashboard to fetch recent events.

The timeline is capped at config.REDIS_EVENT_LIMIT entries to prevent
unbounded growth in long-running daemon sessions.
"""

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from .. import config
from ..backend.models import Incident, IncidentStatus, LogEvent, TraceEvent

_redis: Optional[aioredis.Redis] = None

# Per-incident locks serialise the read-modify-write in update_incident so
# the async interpretation task can't clobber fields written by the locate
# and patch steps (or vice-versa).
_incident_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis


async def save_event(event: LogEvent) -> None:
    r = await get_redis()
    key = f"orqis:event:{event.id}"
    score = event.timestamp.timestamp()
    payload = event.model_dump_json()

    pipe = r.pipeline()
    pipe.set(key, payload, ex=86400)  # TTL: 24h
    pipe.zadd("orqis:events:timeline", {event.id: score})
    # Trim the timeline to the most recent N events
    pipe.zremrangebyrank("orqis:events:timeline", 0, -(config.REDIS_EVENT_LIMIT + 1))
    await pipe.execute()


async def update_interpretation(event_id: str, interpretation: str) -> Optional[LogEvent]:
    """Patch the interpretation field on an existing stored event."""
    r = await get_redis()
    key = f"orqis:event:{event_id}"
    raw = await r.get(key)
    if not raw:
        return None

    data = json.loads(raw)
    data["interpretation"] = interpretation
    await r.set(key, json.dumps(data), keepttl=True)

    return LogEvent(**data)


async def save_trace_event(event: TraceEvent) -> None:
    r = await get_redis()
    key = f"orqis:trace:{event.id}"
    score = event.timestamp.timestamp()
    payload = event.model_dump_json()

    pipe = r.pipeline()
    pipe.set(key, payload, ex=86400)
    pipe.zadd("orqis:traces:timeline", {event.id: score})
    pipe.zremrangebyrank("orqis:traces:timeline", 0, -(config.REDIS_EVENT_LIMIT + 1))
    await pipe.execute()


async def update_trace_interpretation(event_id: str, interpretation: str) -> bool:
    r = await get_redis()
    key = f"orqis:trace:{event_id}"
    raw = await r.get(key)
    if not raw:
        return False
    data = json.loads(raw)
    data["interpretation"] = interpretation
    await r.set(key, json.dumps(data), keepttl=True)
    return True


async def get_recent_traces(limit: int = 100) -> list[TraceEvent]:
    r = await get_redis()
    ids = await r.zrange("orqis:traces:timeline", -limit, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for tid in ids:
        pipe.get(f"orqis:trace:{tid}")
    raws = await pipe.execute()
    events = []
    for raw in raws:
        if raw:
            try:
                events.append(TraceEvent(**json.loads(raw)))
            except Exception:
                pass
    return events


async def save_incident(incident: Incident) -> None:
    r = await get_redis()
    key = f"orqis:incident:{incident.id}"
    score = incident.created_at.timestamp()
    pipe = r.pipeline()
    pipe.set(key, incident.model_dump_json(), ex=604800)  # TTL: 7 days
    pipe.zadd("orqis:incidents:timeline", {incident.id: score})
    await pipe.execute()


async def update_incident(incident_id: str, **fields) -> Optional[Incident]:
    """
    Patch any fields on an existing incident and return the updated model.

    The read-modify-write is held under a per-incident lock so concurrent
    updates (e.g. the async interpretation task vs. the locate/patch steps)
    cannot overwrite each other's fields.
    """
    async with _incident_locks[incident_id]:
        r = await get_redis()
        key = f"orqis:incident:{incident_id}"
        raw = await r.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        data.update(fields)
        updated = Incident(**data)
        await r.set(key, updated.model_dump_json(), keepttl=True)
        return updated


async def get_incident(incident_id: str) -> Optional[Incident]:
    r = await get_redis()
    raw = await r.get(f"orqis:incident:{incident_id}")
    return Incident(**json.loads(raw)) if raw else None


async def clear_all() -> dict:
    """
    Delete every stored incident, log event, and trace event. Used by the demo
    reset so the dashboard (incidents, ACTIVITY log stream, AI CALLS / cost)
    starts completely clean. Returns a count per kind.
    """
    r = await get_redis()
    counts: dict[str, int] = {}
    for kind, prefix, timeline in (
        ("incidents", "orqis:incident:", "orqis:incidents:timeline"),
        ("events", "orqis:event:", "orqis:events:timeline"),
        ("traces", "orqis:trace:", "orqis:traces:timeline"),
    ):
        ids = await r.zrange(timeline, 0, -1)
        pipe = r.pipeline()
        for i in ids:
            pipe.delete(f"{prefix}{i}")
        pipe.delete(timeline)
        await pipe.execute()
        counts[kind] = len(ids)
    return counts


async def get_recent_incidents(limit: int = 50) -> list[Incident]:
    r = await get_redis()
    ids = await r.zrange("orqis:incidents:timeline", -limit, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for iid in ids:
        pipe.get(f"orqis:incident:{iid}")
    raws = await pipe.execute()
    incidents = []
    for raw in raws:
        if raw:
            try:
                incidents.append(Incident(**json.loads(raw)))
            except Exception:
                pass
    return incidents


async def get_recent_events(limit: int = 100) -> list[LogEvent]:
    """Return the most recent `limit` events, newest last."""
    r = await get_redis()
    # zrange with rev=True gives newest first, then we reverse
    ids = await r.zrange("orqis:events:timeline", -limit, -1)
    if not ids:
        return []

    pipe = r.pipeline()
    for event_id in ids:
        pipe.get(f"orqis:event:{event_id}")
    raws = await pipe.execute()

    events = []
    for raw in raws:
        if raw:
            try:
                events.append(LogEvent(**json.loads(raw)))
            except Exception:
                pass

    return events
