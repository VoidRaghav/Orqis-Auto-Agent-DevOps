"""Sync Redis helpers for tenancy tests (avoids asyncio loop clashes with TestClient)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import redis

from orqis import config
from orqis.backend import workspace_auth
from orqis.backend.models import Incident, IncidentStatus
from orqis.backend.tenancy import reset_workspace_id, set_workspace_id, tenant_prefix

_SESSION_TTL = 60 * 60 * 24 * 14
_INCIDENT_TTL = 604800


def sync_redis() -> redis.Redis:
    return redis.from_url(config.REDIS_URL, decode_responses=True)


def redis_available() -> bool:
    try:
        sync_redis().ping()
        return True
    except Exception:
        return False


def session_cookies(workspace_id: str, login: str = "user", github_id: int = 42) -> dict[str, str]:
    sid = workspace_auth.create_session_id()
    payload = {
        "workspace_id": workspace_id,
        "github_id": github_id,
        "login": login,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = sync_redis()
    ws_key = f"orqis:workspace:{workspace_id}"
    if not r.exists(ws_key):
        r.set(
            ws_key,
            json.dumps(
                {
                    "id": workspace_id,
                    "name": f"{login}'s workspace",
                    "owner_github_id": github_id,
                    "owner_login": login,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        member = json.dumps(
            {
                "github_id": github_id,
                "login": login,
                "role": "owner",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        r.hset(f"orqis:workspace:{workspace_id}:members", str(github_id), member)
    r.set(f"orqis:session:{sid}", json.dumps(payload), ex=_SESSION_TTL)
    return {config.SESSION_COOKIE_NAME: workspace_auth.sign_session_cookie(sid)}


def create_api_key_sync(workspace_id: str, label: str = "test") -> str:
    from orqis.backend.workspace_auth import _hash_secret

    full, prefix = workspace_auth.generate_api_key()
    key_id = secrets.token_hex(8)
    meta: dict[str, Any] = {
        "id": key_id,
        "workspace_id": workspace_id,
        "label": label,
        "prefix": prefix,
        "key_hash": _hash_secret(full),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = sync_redis()
    r.set(f"orqis:apikey:{_hash_secret(full)}", workspace_id)
    r.set(f"orqis:workspace:{workspace_id}:apikey:{key_id}", json.dumps(meta))
    return full


def seed_incident_sync(workspace_id: str, incident_id: str, message: str) -> None:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        inc = Incident(
            id=incident_id,
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="http-test",
            error_message=message,
            source="test",
        )
        r = sync_redis()
        key = f"{prefix}incident:{incident_id}"
        timeline = f"{prefix}incidents:timeline"
        pipe = r.pipeline()
        pipe.set(key, inc.model_dump_json(), ex=_INCIDENT_TTL)
        pipe.zadd(timeline, {incident_id: inc.created_at.timestamp()})
        pipe.execute()
    finally:
        reset_workspace_id(tok)


def get_incident_sync(workspace_id: str, incident_id: str) -> Optional[Incident]:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        raw = sync_redis().get(f"{prefix}incident:{incident_id}")
        return Incident(**json.loads(raw)) if raw else None
    finally:
        reset_workspace_id(tok)


def list_incident_ids_sync(workspace_id: str, limit: int = 50) -> list[str]:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        return sync_redis().zrange(f"{prefix}incidents:timeline", -limit, -1)
    finally:
        reset_workspace_id(tok)


def save_settings_sync(workspace_id: str, patch: dict[str, Any]) -> None:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        key = f"{prefix}settings"
        r = sync_redis()
        raw = r.get(key)
        data = json.loads(raw) if raw else {}
        data.update(patch)
        r.set(key, json.dumps(data))
    finally:
        reset_workspace_id(tok)


def get_settings_sync(workspace_id: str) -> dict[str, Any]:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        raw = sync_redis().get(f"{prefix}settings")
        return json.loads(raw) if raw else {}
    finally:
        reset_workspace_id(tok)


def clear_workspace_sync(workspace_id: str) -> None:
    tok = set_workspace_id(workspace_id)
    try:
        prefix = tenant_prefix()
        r = sync_redis()
        for id_prefix, timeline in (
            (f"{prefix}incident:", f"{prefix}incidents:timeline"),
            (f"{prefix}event:", f"{prefix}events:timeline"),
            (f"{prefix}trace:", f"{prefix}traces:timeline"),
            (f"{prefix}change:", f"{prefix}changes:timeline"),
        ):
            ids = r.zrange(timeline, 0, -1)
            if not ids:
                continue
            pipe = r.pipeline()
            for iid in ids:
                pipe.delete(f"{id_prefix}{iid}")
            pipe.delete(timeline)
            pipe.execute()
    finally:
        reset_workspace_id(tok)
