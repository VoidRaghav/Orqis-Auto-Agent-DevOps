"""
Durable persistence for the records that must survive a restart.

Redis stays the fast live/cache layer; Postgres is the system of record for the
things a real user cannot afford to lose when the process restarts or Redis is
wiped: incidents, the CHANGES audit trail, and workspace settings (including the
GitHub installation). Every helper is a no-op when DATABASE_URL is unset, so
single-tenant local dev keeps running purely on Redis.

Flow:
  - writes: store.py mirrors each durable write here (Postgres) after Redis.
  - restart: rehydrate_redis() reloads the durable records from Postgres back
    into Redis, so the dashboard and the merge-webhook index are intact even
    though Redis lost everything.
"""

import json
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .. import config

logger = logging.getLogger("orqis.durable")

# Single-tenant today; when auth lands this becomes the resolved tenant id.
DEFAULT_TENANT = "default"


def enabled() -> bool:
    return bool(config.DATABASE_URL)


def _status_str(incident) -> str:
    s = incident.status
    return s.value if hasattr(s, "value") else str(s)


def _err_str(incident) -> Optional[str]:
    e = incident.error_type
    if e is None:
        return None
    return e.value if hasattr(e, "value") else str(e)


async def upsert_incident(incident) -> None:
    """Insert or update an incident row. Never raises — a durability hiccup must
    not break the live ingest path (the record is still in Redis for the
    session; it will be reconciled on the next write)."""
    if not enabled():
        return
    try:
        from . import db

        data = incident.model_dump(mode="json")
        values = dict(
            id=incident.id,
            tenant_id=DEFAULT_TENANT,
            status=_status_str(incident),
            error_type=_err_str(incident),
            source=incident.source,
            repo_full_name=incident.repo_full_name,
            pr_number=incident.pr_number,
            created_at=incident.created_at,
            resolved_at=incident.resolved_at,
            data=data,
        )
        stmt = pg_insert(db.IncidentRow).values(**values).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "status": values["status"],
                "error_type": values["error_type"],
                "source": values["source"],
                "repo_full_name": values["repo_full_name"],
                "pr_number": values["pr_number"],
                "resolved_at": values["resolved_at"],
                "data": data,
            },
        )
        async with db.session() as s:
            await s.execute(stmt)
    except Exception:
        logger.warning("durable upsert_incident failed for %s", getattr(incident, "id", "?"), exc_info=True)


async def record_change(entry) -> None:
    """Append a change-log entry (idempotent on id)."""
    if not enabled():
        return
    try:
        from . import db

        stmt = pg_insert(db.ChangeRow).values(
            id=entry.id,
            tenant_id=DEFAULT_TENANT,
            incident_id=entry.incident_id,
            action=entry.action,
            created_at=entry.timestamp,
            data=entry.model_dump(mode="json"),
        ).on_conflict_do_nothing(index_elements=["id"])
        async with db.session() as s:
            await s.execute(stmt)
    except Exception:
        logger.warning("durable record_change failed for %s", getattr(entry, "id", "?"), exc_info=True)


async def save_settings(settings: dict) -> None:
    """Upsert the full workspace settings blob (install, repo maps, toggles)."""
    if not enabled():
        return
    try:
        from . import db

        stmt = pg_insert(db.WorkspaceSettings).values(
            tenant_id=DEFAULT_TENANT, data=settings
        ).on_conflict_do_update(
            index_elements=["tenant_id"], set_={"data": settings}
        )
        async with db.session() as s:
            await s.execute(stmt)
    except Exception:
        logger.warning("durable save_settings failed", exc_info=True)


async def clear_all() -> None:
    """Delete durable incidents + changes for the tenant (demo reset ?clear)."""
    if not enabled():
        return
    try:
        from . import db

        async with db.session() as s:
            await s.execute(delete(db.IncidentRow).where(db.IncidentRow.tenant_id == DEFAULT_TENANT))
            await s.execute(delete(db.ChangeRow).where(db.ChangeRow.tenant_id == DEFAULT_TENANT))
    except Exception:
        logger.warning("durable clear_all failed", exc_info=True)


async def rehydrate_redis(limit: int = 500) -> dict:
    """
    Reload durable records from Postgres into Redis after a restart so the live
    layer is whole again: recent incidents + their timeline, the PR->incident
    index for still-open PRs (so a merge webhook can resolve), recent changes,
    and workspace settings. Returns per-kind counts.
    """
    if not enabled():
        return {}

    from . import db, store
    from .models import ChangeLogEntry, Incident

    r = await store.get_redis()
    counts: dict = {}

    async with db.session() as s:
        rows = (
            await s.execute(
                select(db.IncidentRow)
                .where(db.IncidentRow.tenant_id == DEFAULT_TENANT)
                .order_by(db.IncidentRow.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        pipe = r.pipeline()
        for row in rows:
            try:
                inc = Incident(**row.data)
            except Exception:
                continue
            key = f"orqis:incident:{inc.id}"
            # No TTL on rehydrate — Postgres is the source of truth; Redis just
            # serves the dashboard. The normal lifecycle re-arms TTLs on new work.
            pipe.set(key, inc.model_dump_json())
            pipe.zadd("orqis:incidents:timeline", {inc.id: inc.created_at.timestamp()})
            if inc.pr_number and inc.repo_full_name and inc.status not in ("resolved", "dismissed"):
                pipe.set(f"orqis:pr:{inc.repo_full_name}#{inc.pr_number}", inc.id)
        await pipe.execute()
        counts["incidents"] = len(rows)

        crows = (
            await s.execute(
                select(db.ChangeRow)
                .where(db.ChangeRow.tenant_id == DEFAULT_TENANT)
                .order_by(db.ChangeRow.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        pipe = r.pipeline()
        for row in crows:
            try:
                ce = ChangeLogEntry(**row.data)
            except Exception:
                continue
            pipe.set(f"orqis:change:{ce.id}", ce.model_dump_json())
            pipe.zadd("orqis:changes:timeline", {ce.id: ce.timestamp.timestamp()})
        await pipe.execute()
        counts["changes"] = len(crows)

        srow = (
            await s.execute(
                select(db.WorkspaceSettings).where(db.WorkspaceSettings.tenant_id == DEFAULT_TENANT)
            )
        ).scalar_one_or_none()
        if srow and srow.data:
            await r.set("orqis:settings:workspace", json.dumps(srow.data))
            counts["settings"] = 1

    return counts
