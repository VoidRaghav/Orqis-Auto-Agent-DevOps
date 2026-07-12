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
from typing import Optional, Union

import redis.asyncio as aioredis

from .. import config
from ..backend import durable
from ..backend.models import ChangeLogEntry, Incident, IncidentStatus, LogEvent, TraceEvent
from .tenancy import get_workspace_id, tenant_prefix

_redis_by_loop: dict[int, aioredis.Redis] = {}

# Per-incident locks serialise the read-modify-write in update_incident so
# the async interpretation task can't clobber fields written by the locate
# and patch steps (or vice-versa).
_incident_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _tp() -> str:
    return tenant_prefix()


def _settings_key() -> str:
    return f"{_tp()}settings"


async def get_redis() -> aioredis.Redis:
    loop_id = id(asyncio.get_running_loop())
    client = _redis_by_loop.get(loop_id)
    if client is None:
        client = await aioredis.from_url(config.REDIS_URL, decode_responses=True)
        _redis_by_loop[loop_id] = client
    return client


async def reset_redis_connection() -> None:
    """Close Redis pools for all cached event loops (test harness)."""
    for loop_id, client in list(_redis_by_loop.items()):
        await client.aclose()
        del _redis_by_loop[loop_id]


async def scan_keys(pattern: str, *, count: int = 100) -> list[str]:
    """Iterate Redis keys matching `pattern` without blocking KEYS."""
    r = await get_redis()
    found: list[str] = []
    cursor: Union[int, str] = 0
    while True:
        cursor, batch = await r.scan(cursor=cursor, match=pattern, count=count)
        found.extend(batch)
        if cursor == 0 or cursor == "0":
            break
    return found


async def save_event(event: LogEvent) -> None:
    r = await get_redis()
    tp = _tp()
    key = f"{tp}event:{event.id}"
    score = event.timestamp.timestamp()
    timeline = f"{tp}events:timeline"
    payload = event.model_dump_json()

    pipe = r.pipeline()
    pipe.set(key, payload, ex=86400)  # TTL: 24h
    pipe.zadd(timeline, {event.id: score})
    # Trim the timeline to the most recent N events
    pipe.zremrangebyrank(timeline, 0, -(config.REDIS_EVENT_LIMIT + 1))
    await pipe.execute()


async def update_interpretation(event_id: str, interpretation: str) -> Optional[LogEvent]:
    """Patch the interpretation field on an existing stored event."""
    r = await get_redis()
    key = f"{_tp()}event:{event_id}"
    raw = await r.get(key)
    if not raw:
        return None

    data = json.loads(raw)
    data["interpretation"] = interpretation
    await r.set(key, json.dumps(data), keepttl=True)

    return LogEvent(**data)


async def save_trace_event(event: TraceEvent) -> None:
    r = await get_redis()
    tp = _tp()
    key = f"{tp}trace:{event.id}"
    score = event.timestamp.timestamp()
    timeline = f"{tp}traces:timeline"
    payload = event.model_dump_json()

    pipe = r.pipeline()
    pipe.set(key, payload, ex=86400)
    pipe.zadd(timeline, {event.id: score})
    pipe.zremrangebyrank(timeline, 0, -(config.REDIS_EVENT_LIMIT + 1))
    await pipe.execute()


async def update_trace_interpretation(event_id: str, interpretation: str) -> bool:
    r = await get_redis()
    key = f"{_tp()}trace:{event_id}"
    raw = await r.get(key)
    if not raw:
        return False
    data = json.loads(raw)
    data["interpretation"] = interpretation
    await r.set(key, json.dumps(data), keepttl=True)
    return True


async def get_recent_traces(limit: int = 100) -> list[TraceEvent]:
    r = await get_redis()
    timeline = f"{_tp()}traces:timeline"
    ids = await r.zrange(timeline, -limit, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for tid in ids:
        pipe.get(f"{_tp()}trace:{tid}")
    raws = await pipe.execute()
    events = []
    for raw in raws:
        if raw:
            try:
                events.append(TraceEvent(**json.loads(raw)))
            except Exception:
                pass
    return events


_INCIDENT_TTL_SECONDS = 604800  # 7 days


async def save_incident(incident: Incident) -> None:
    r = await get_redis()
    tp = _tp()
    key = f"{tp}incident:{incident.id}"
    score = incident.created_at.timestamp()
    timeline = f"{tp}incidents:timeline"
    pipe = r.pipeline()
    pipe.set(key, incident.model_dump_json(), ex=_INCIDENT_TTL_SECONDS)
    pipe.zadd(timeline, {incident.id: score})
    await pipe.execute()
    await durable.upsert_incident(incident)


async def update_incident(incident_id: str, **fields) -> Optional[Incident]:
    """
    Patch any fields on an existing incident and return the updated model.

    The read-modify-write is held under a per-incident lock so concurrent
    updates (e.g. the async interpretation task vs. the locate/patch steps)
    cannot overwrite each other's fields.
    """
    async with _incident_locks[incident_id]:
        r = await get_redis()
        key = f"{_tp()}incident:{incident_id}"
        raw = await r.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        data.update(fields)
        updated = Incident(**data)
        await r.set(key, updated.model_dump_json(), keepttl=True)
        await durable.upsert_incident(updated)
        return updated


async def get_incident(incident_id: str) -> Optional[Incident]:
    r = await get_redis()
    raw = await r.get(f"{_tp()}incident:{incident_id}")
    return Incident(**json.loads(raw)) if raw else None


async def clear_all() -> dict:
    """
    Delete every stored incident, log event, and trace event for the active
    workspace. Used by the demo reset so the dashboard starts clean.
    """
    r = await get_redis()
    tp = _tp()
    counts: dict[str, int] = {}
    for kind, prefix, timeline in (
        ("incidents", f"{tp}incident:", f"{tp}incidents:timeline"),
        ("events", f"{tp}event:", f"{tp}events:timeline"),
        ("traces", f"{tp}trace:", f"{tp}traces:timeline"),
        ("changes", f"{tp}change:", f"{tp}changes:timeline"),
    ):
        ids = await r.zrange(timeline, 0, -1)
        pipe = r.pipeline()
        for i in ids:
            pipe.delete(f"{prefix}{i}")
        pipe.delete(timeline)
        await pipe.execute()
        counts[kind] = len(ids)
    await durable.clear_all()
    return counts


async def get_recent_incidents(limit: int = 50) -> list[Incident]:
    r = await get_redis()
    timeline = f"{_tp()}incidents:timeline"
    ids = await r.zrange(timeline, -limit, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for iid in ids:
        pipe.get(f"{_tp()}incident:{iid}")
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
    timeline = f"{_tp()}events:timeline"
    ids = await r.zrange(timeline, -limit, -1)
    if not ids:
        return []

    pipe = r.pipeline()
    for event_id in ids:
        pipe.get(f"{_tp()}event:{event_id}")
    raws = await pipe.execute()

    events = []
    for raw in raws:
        if raw:
            try:
                events.append(LogEvent(**json.loads(raw)))
            except Exception:
                pass

    return events


# --- Change log (audit trail of every fix Orqis makes) -----------------------

async def save_change(entry: ChangeLogEntry) -> None:
    r = await get_redis()
    tp = _tp()
    key = f"{tp}change:{entry.id}"
    score = entry.timestamp.timestamp()
    timeline = f"{tp}changes:timeline"
    pipe = r.pipeline()
    pipe.set(key, entry.model_dump_json(), ex=_INCIDENT_TTL_SECONDS)
    pipe.zadd(timeline, {entry.id: score})
    pipe.zremrangebyrank(timeline, 0, -(config.REDIS_EVENT_LIMIT + 1))
    await pipe.execute()
    await durable.record_change(entry)


async def get_recent_changes(limit: int = 100) -> list[ChangeLogEntry]:
    r = await get_redis()
    timeline = f"{_tp()}changes:timeline"
    ids = await r.zrange(timeline, -limit, -1)
    if not ids:
        return []
    pipe = r.pipeline()
    for cid in ids:
        pipe.get(f"{_tp()}change:{cid}")
    raws = await pipe.execute()
    out = []
    for raw in raws:
        if raw:
            try:
                out.append(ChangeLogEntry(**json.loads(raw)))
            except Exception:
                pass
    return out


# --- Incident TTL lifecycle (P1) ---------------------------------------------

async def persist_incident(incident_id: str) -> None:
    """
    Remove the TTL on an incident so it survives until the PR is merged or
    dismissed. Called when an incident enters pr_open — a user may take days to
    merge, and the merge webhook must still find the incident.
    """
    r = await get_redis()
    await r.persist(f"{_tp()}incident:{incident_id}")


async def set_incident_ttl(incident_id: str, seconds: int = _INCIDENT_TTL_SECONDS) -> None:
    """Re-arm the rolling TTL once an incident reaches a terminal state."""
    r = await get_redis()
    await r.expire(f"{_tp()}incident:{incident_id}", seconds)


# --- PR -> incident reverse index (P3) ---------------------------------------

def _pr_index_key(repo: str, pr_number: int) -> str:
    return f"{_tp()}pr:{repo}#{pr_number}"


async def set_pr_index(repo: str, pr_number: int, incident_id: str) -> None:
    """Map a PR back to the incident it fixes so the merge webhook can resolve it."""
    r = await get_redis()
    await r.set(_pr_index_key(repo, pr_number), incident_id)


async def get_incident_id_by_pr(repo: str, pr_number: int) -> Optional[str]:
    r = await get_redis()
    return await r.get(_pr_index_key(repo, pr_number))


async def clear_pr_index(repo: str, pr_number: int) -> None:
    r = await get_redis()
    await r.delete(_pr_index_key(repo, pr_number))


async def finalize_pr_open(
    incident_id: str,
    repo: str,
    pr_number: int,
    **fields,
) -> Optional[Incident]:
    """
    Atomically persist pr_open state: PR index, drop incident TTL, and patch fields
    under the per-incident lock (C5).
    """
    async with _incident_locks[incident_id]:
        r = await get_redis()
        key = f"{_tp()}incident:{incident_id}"
        raw = await r.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        # The positional pr_number is the single source of truth — persist it on
        # the incident too (callers pass it once, here).
        fields.setdefault("pr_number", pr_number)
        data.update(fields)
        updated = Incident(**data)
        pipe = r.pipeline(transaction=True)
        pipe.set(_pr_index_key(repo, pr_number), incident_id)
        pipe.persist(key)
        pipe.set(key, updated.model_dump_json())
        await pipe.execute()
        await durable.upsert_incident(updated)
        return updated


# --- Redis-backed dedup fingerprint (P5) -------------------------------------

async def dedup_get(fingerprint: str) -> Optional[str]:
    """Return the incident_id for a fingerprint still inside the dedup window."""
    r = await get_redis()
    return await r.get(f"{_tp()}fp:{fingerprint}")


async def dedup_set(fingerprint: str, incident_id: str, ttl_seconds: int) -> None:
    """Record a fingerprint -> incident_id mapping with the dedup-window TTL."""
    r = await get_redis()
    await r.set(f"{_tp()}fp:{fingerprint}", incident_id, ex=ttl_seconds)


async def dedup_clear(fingerprint: str) -> None:
    r = await get_redis()
    await r.delete(f"{_tp()}fp:{fingerprint}")


# --- Webhook delivery replay dedup (S6) --------------------------------------

async def delivery_seen(guid: str, ttl_seconds: int = 86400) -> bool:
    """
    Atomically record a webhook delivery GUID. Returns True if we've already
    processed this delivery (replay), False if it is new.
    """
    if not guid:
        return False
    r = await get_redis()
    # Global dedup — webhooks arrive before workspace context is known.
    was_new = await r.set(f"orqis:delivery:{guid}", "1", nx=True, ex=ttl_seconds)
    return not bool(was_new)


# --- Workspace settings (P2 — non-expiring) ----------------------------------

_DEFAULT_SETTINGS: dict = {
    "installation_id": None,
    "account_login": None,
    "repos": [],
    "source_repo_map": {},
    "default_repo": "",
    "default_branch": "main",
    "repo_default_branches": {},
    "hot_reload_webhook_url": "",
    "auto_merge_enabled": False,
    "pr_low_confidence": False,
    "notification_webhook_url": "",
    "notification_slack_url": "",
}


async def get_settings() -> dict:
    """Return workspace settings, merged over defaults. Never expires."""
    r = await get_redis()
    raw = await r.get(_settings_key())
    settings = dict(_DEFAULT_SETTINGS)
    if raw:
        try:
            settings.update(json.loads(raw))
        except Exception:
            pass
    return settings


async def save_settings(patch: dict) -> dict:
    """Merge a partial update into workspace settings and persist (no TTL)."""
    r = await get_redis()
    current = await get_settings()
    current.update({k: v for k, v in patch.items() if k in _DEFAULT_SETTINGS})
    await r.set(_settings_key(), json.dumps(current))
    await durable.save_settings(current)
    return current
