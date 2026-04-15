"""
Redis-backed event store.

Each LogEvent is stored as a JSON hash at key orqis:event:<id>.
A sorted set orqis:events:timeline (score = unix timestamp) provides
ordered access for the dashboard to fetch recent events.

The timeline is capped at config.REDIS_EVENT_LIMIT entries to prevent
unbounded growth in long-running daemon sessions.
"""

import json
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from .. import config
from ..backend.models import LogEvent

_redis: Optional[aioredis.Redis] = None


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
