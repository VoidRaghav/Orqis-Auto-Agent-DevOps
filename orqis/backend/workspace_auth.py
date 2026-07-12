"""
Workspace identity: users, sessions, API keys, GitHub install index.

Durable workspace metadata lives in Redis (no new DB dependency). Operational
data (incidents, traces) uses tenant-prefixed keys via tenancy.tenant_prefix().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

from . import store
from .tenancy import DEFAULT_WORKSPACE_ID

_SESSION_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 days
_INVITE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
_API_KEY_PREFIX = "orqs_"
_MEMBER_ROLES = frozenset({"owner", "member"})


def _hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _session_key(session_id: str) -> str:
    return f"orqis:session:{session_id}"


def _user_key(github_id: int) -> str:
    return f"orqis:user:{github_id}"


def _workspace_key(workspace_id: str) -> str:
    return f"orqis:workspace:{workspace_id}"


def _apikey_index_key(raw_key: str) -> str:
    return f"orqis:apikey:{_hash_secret(raw_key)}"


def _install_index_key(installation_id: int) -> str:
    return f"orqis:install:{installation_id}"


def _members_key(workspace_id: str) -> str:
    return f"orqis:workspace:{workspace_id}:members"


def _invite_key(token: str) -> str:
    return f"orqis:invite:{token}"


def _workspace_invites_key(workspace_id: str) -> str:
    return f"orqis:workspace:{workspace_id}:invites"


def generate_api_key() -> tuple[str, str]:
    """Return (full_key, display_prefix) — show full key once to the user."""
    raw = _API_KEY_PREFIX + secrets.token_urlsafe(24)
    return raw, raw[:12] + "…"


async def create_api_key(workspace_id: str, label: str = "default") -> dict[str, Any]:
    full, prefix = generate_api_key()
    r = await store.get_redis()
    key_id = secrets.token_hex(8)
    meta = {
        "id": key_id,
        "workspace_id": workspace_id,
        "label": label,
        "prefix": prefix,
        "key_hash": _hash_secret(full),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    pipe = r.pipeline()
    pipe.set(_apikey_index_key(full), workspace_id)
    pipe.set(
        f"orqis:workspace:{workspace_id}:apikey:{key_id}",
        json.dumps(meta),
    )
    await pipe.execute()
    return {"key": full, "meta": meta}


async def revoke_api_key(workspace_id: str, key_id: str) -> bool:
    r = await store.get_redis()
    raw = await r.get(f"orqis:workspace:{workspace_id}:apikey:{key_id}")
    if not raw:
        return False
    try:
        meta = json.loads(raw)
        key_hash = meta.get("key_hash")
        if key_hash:
            await r.delete(f"orqis:apikey:{key_hash}")
    except Exception:
        pass
    await r.delete(f"orqis:workspace:{workspace_id}:apikey:{key_id}")
    return True


async def list_api_keys(workspace_id: str) -> list[dict[str, Any]]:
    r = await store.get_redis()
    keys = await store.scan_keys(f"orqis:workspace:{workspace_id}:apikey:*")
    out: list[dict[str, Any]] = []
    for k in keys:
        raw = await r.get(k)
        if raw:
            try:
                out.append(json.loads(raw))
            except Exception:
                pass
    return out


async def resolve_workspace_from_api_key(raw_key: str) -> Optional[str]:
    if not raw_key or not raw_key.startswith(_API_KEY_PREFIX):
        return None
    r = await store.get_redis()
    return await r.get(_apikey_index_key(raw_key))


def create_session_id() -> str:
    return secrets.token_urlsafe(32)


async def save_session(
    session_id: str,
    *,
    workspace_id: str,
    github_id: int,
    login: str,
) -> None:
    r = await store.get_redis()
    payload = {
        "workspace_id": workspace_id,
        "github_id": github_id,
        "login": login,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await r.set(_session_key(session_id), json.dumps(payload), ex=_SESSION_TTL_SECONDS)


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    if not session_id:
        return None
    r = await store.get_redis()
    raw = await r.get(_session_key(session_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def delete_session(session_id: str) -> None:
    r = await store.get_redis()
    await r.delete(_session_key(session_id))


async def get_or_create_user_workspace(
    github_id: int,
    login: str,
    avatar_url: str = "",
) -> tuple[str, dict[str, Any]]:
    """
    First login creates a workspace owned by this GitHub user.
    Returns (workspace_id, workspace_record).
    """
    r = await store.get_redis()
    user_raw = await r.get(_user_key(github_id))
    if user_raw:
        user = json.loads(user_raw)
        wid = user["primary_workspace_id"]
        ws_raw = await r.get(_workspace_key(wid))
        if ws_raw:
            return wid, json.loads(ws_raw)

    workspace_id = secrets.token_hex(12)
    workspace = {
        "id": workspace_id,
        "name": f"{login}'s workspace",
        "owner_github_id": github_id,
        "owner_login": login,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    user = {
        "github_id": github_id,
        "login": login,
        "avatar_url": avatar_url,
        "primary_workspace_id": workspace_id,
        "workspace_ids": [workspace_id],
    }
    pipe = r.pipeline()
    pipe.set(_workspace_key(workspace_id), json.dumps(workspace))
    pipe.set(_user_key(github_id), json.dumps(user))
    await pipe.execute()
    await add_member(workspace_id, github_id, login, role="owner")
    return workspace_id, workspace


async def add_member(
    workspace_id: str,
    github_id: int,
    login: str,
    *,
    role: str = "member",
) -> None:
    if role not in _MEMBER_ROLES:
        role = "member"
    r = await store.get_redis()
    payload = json.dumps(
        {
            "github_id": github_id,
            "login": login,
            "role": role,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await r.hset(_members_key(workspace_id), str(github_id), payload)


async def ensure_owner_member(workspace_id: str) -> None:
    """Backfill owner into members hash for workspaces created before invites."""
    ws = await get_workspace(workspace_id)
    if not ws:
        return
    owner_id = ws.get("owner_github_id")
    if not owner_id:
        return
    r = await store.get_redis()
    if await r.hexists(_members_key(workspace_id), str(owner_id)):
        return
    await add_member(
        workspace_id,
        int(owner_id),
        ws.get("owner_login", "owner"),
        role="owner",
    )


async def is_workspace_member(workspace_id: str, github_id: int) -> bool:
    await ensure_owner_member(workspace_id)
    r = await store.get_redis()
    return bool(await r.hexists(_members_key(workspace_id), str(github_id)))


async def get_member_role(workspace_id: str, github_id: int) -> Optional[str]:
    await ensure_owner_member(workspace_id)
    r = await store.get_redis()
    raw = await r.hget(_members_key(workspace_id), str(github_id))
    if not raw:
        return None
    try:
        return json.loads(raw).get("role")
    except Exception:
        return None


async def list_members(workspace_id: str) -> list[dict[str, Any]]:
    await ensure_owner_member(workspace_id)
    r = await store.get_redis()
    raw_map = await r.hgetall(_members_key(workspace_id))
    out: list[dict[str, Any]] = []
    for raw in raw_map.values():
        try:
            out.append(json.loads(raw))
        except Exception:
            pass
    out.sort(key=lambda m: (0 if m.get("role") == "owner" else 1, m.get("login", "")))
    return out


async def create_invite(
    workspace_id: str,
    *,
    created_by_github_id: int,
    created_by_login: str,
    role: str = "member",
) -> dict[str, Any]:
    role = role if role in _MEMBER_ROLES and role != "owner" else "member"
    token = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    meta = {
        "token": token,
        "workspace_id": workspace_id,
        "role": role,
        "created_by_github_id": created_by_github_id,
        "created_by_login": created_by_login,
        "created_at": now.isoformat(),
        "expires_at": (now.timestamp() + _INVITE_TTL_SECONDS),
    }
    r = await store.get_redis()
    pipe = r.pipeline()
    pipe.set(_invite_key(token), json.dumps(meta), ex=_INVITE_TTL_SECONDS)
    pipe.zadd(_workspace_invites_key(workspace_id), {token: now.timestamp()})
    await pipe.execute()
    return meta


async def get_invite(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    r = await store.get_redis()
    raw = await r.get(_invite_key(token))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def list_invites(workspace_id: str) -> list[dict[str, Any]]:
    r = await store.get_redis()
    tokens = await r.zrange(_workspace_invites_key(workspace_id), 0, -1)
    out: list[dict[str, Any]] = []
    for tok in tokens:
        inv = await get_invite(tok)
        if inv:
            out.append(inv)
    return out


async def revoke_invite(workspace_id: str, token: str) -> bool:
    inv = await get_invite(token)
    if not inv or inv.get("workspace_id") != workspace_id:
        return False
    r = await store.get_redis()
    pipe = r.pipeline()
    pipe.delete(_invite_key(token))
    pipe.zrem(_workspace_invites_key(workspace_id), token)
    await pipe.execute()
    return True


async def accept_invite(
    token: str,
    github_id: int,
    login: str,
    avatar_url: str = "",
) -> tuple[str, dict[str, Any]]:
    """
    Join an existing workspace via invite token.
    Creates or updates the user record; does not create a new workspace.
    """
    inv = await get_invite(token)
    if not inv:
        raise ValueError("invite not found or expired")
    workspace_id = inv["workspace_id"]
    ws = await get_workspace(workspace_id)
    if not ws:
        raise ValueError("workspace not found")

    role = inv.get("role", "member")
    await add_member(workspace_id, github_id, login, role=role)

    r = await store.get_redis()
    user_raw = await r.get(_user_key(github_id))
    if user_raw:
        user = json.loads(user_raw)
        ids = list(user.get("workspace_ids") or [])
        if workspace_id not in ids:
            ids.append(workspace_id)
        user["workspace_ids"] = ids
        user["login"] = login
        if avatar_url:
            user["avatar_url"] = avatar_url
    else:
        user = {
            "github_id": github_id,
            "login": login,
            "avatar_url": avatar_url,
            "primary_workspace_id": workspace_id,
            "workspace_ids": [workspace_id],
        }
    await r.set(_user_key(github_id), json.dumps(user))
    await revoke_invite(workspace_id, token)
    return workspace_id, ws


async def get_workspace(workspace_id: str) -> Optional[dict[str, Any]]:
    r = await store.get_redis()
    raw = await r.get(_workspace_key(workspace_id))
    return json.loads(raw) if raw else None


async def set_install_workspace(installation_id: int, workspace_id: str) -> None:
    r = await store.get_redis()
    await r.set(_install_index_key(installation_id), workspace_id)


async def get_workspace_for_installation(installation_id: int) -> Optional[str]:
    r = await store.get_redis()
    return await r.get(_install_index_key(installation_id))


async def clear_install_workspace(installation_id: int) -> None:
    r = await store.get_redis()
    await r.delete(_install_index_key(installation_id))


def sign_session_cookie(session_id: str) -> str:
    from .. import config

    secret = config.SESSION_SECRET.encode()
    sig = hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()
    return f"{session_id}.{sig}"


def verify_session_cookie(value: str) -> Optional[str]:
    from .. import config

    if not value or "." not in value:
        return None
    session_id, sig = value.rsplit(".", 1)
    secret = config.SESSION_SECRET.encode()
    expected = hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return session_id


async def migrate_legacy_keys_to_default_workspace() -> dict[str, int]:
    """
    One-time copy of pre-tenant Redis keys into orqis:t:default:*.
    Safe to call on every startup — no-ops when legacy timelines are empty.
    """
    r = await store.get_redis()
    prefix = f"orqis:t:{DEFAULT_WORKSPACE_ID}:"
    legacy_timeline = await r.zrange("orqis:incidents:timeline", 0, -1)
    if not legacy_timeline:
        return {"migrated": 0}
    new_timeline = await r.zrange(f"{prefix}incidents:timeline", 0, -1)
    if new_timeline:
        return {"migrated": 0, "skipped": "already migrated"}

    counts = {"incidents": 0, "events": 0, "traces": 0, "changes": 0, "settings": 0}
    mappings = [
        ("orqis:incident:", f"{prefix}incident:", "orqis:incidents:timeline", f"{prefix}incidents:timeline", "incidents"),
        ("orqis:event:", f"{prefix}event:", "orqis:events:timeline", f"{prefix}events:timeline", "events"),
        ("orqis:trace:", f"{prefix}trace:", "orqis:traces:timeline", f"{prefix}traces:timeline", "traces"),
        ("orqis:change:", f"{prefix}change:", "orqis:changes:timeline", f"{prefix}changes:timeline", "changes"),
    ]
    for old_p, new_p, old_tl, new_tl, kind in mappings:
        ids = await r.zrange(old_tl, 0, -1)
        pipe = r.pipeline()
        for i in ids:
            raw = await r.get(f"{old_p}{i}")
            if raw:
                pipe.set(f"{new_p}{i}", raw)
                counts[kind] += 1
        if ids:
            for i in ids:
                score = await r.zscore(old_tl, i)
                if score is not None:
                    pipe.zadd(new_tl, {i: score})
        await pipe.execute()

    settings_raw = await r.get("orqis:settings:workspace")
    if settings_raw:
        await r.set(f"{prefix}settings", settings_raw)
        counts["settings"] = 1

    # PR index and dedup keys — copy with same suffix
    for key in await store.scan_keys("orqis:pr:*"):
        val = await r.get(key)
        if val:
            suffix = key[len("orqis:"):]
            await r.set(f"{prefix}{suffix}", val)
    for key in await store.scan_keys("orqis:fp:*"):
        val = await r.get(key)
        if val:
            suffix = key[len("orqis:"):]
            await r.set(f"{prefix}{suffix}", val)

    return counts
