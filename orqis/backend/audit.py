"""Append-only audit log for workspace write actions (multi-tenant hosted)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from .store import get_redis
from .tenancy import get_workspace_id

_MAX_ENTRIES = 500


async def record(
    action: str,
    *,
    actor: str,
    resource_type: str = "",
    resource_id: str = "",
    ip: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    from .. import config

    if not config.MULTI_TENANT:
        return

    wid = get_workspace_id()
    entry = {
        "id": secrets.token_hex(8),
        "workspace_id": wid,
        "action": action,
        "actor": actor,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "detail": detail or {},
        "ip": ip or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    r = await get_redis()
    key = f"orqis:workspace:{wid}:audit:{entry['id']}"
    timeline = f"orqis:workspace:{wid}:audit:timeline"
    score = datetime.now(timezone.utc).timestamp()
    pipe = r.pipeline()
    pipe.set(key, json.dumps(entry), ex=60 * 60 * 24 * 30)
    pipe.zadd(timeline, {entry["id"]: score})
    pipe.zremrangebyrank(timeline, 0, -(_MAX_ENTRIES + 1))
    await pipe.execute()


async def list_recent(workspace_id: str, limit: int = 50) -> list[dict[str, Any]]:
    r = await get_redis()
    timeline = f"orqis:workspace:{workspace_id}:audit:timeline"
    ids = await r.zrange(timeline, -limit, -1)
    out: list[dict[str, Any]] = []
    for iid in ids:
        raw = await r.get(f"orqis:workspace:{workspace_id}:audit:{iid}")
        if raw:
            try:
                out.append(json.loads(raw))
            except Exception:
                pass
    return out
