"""
Per-tenant API-key auth for the ingest endpoints.

The SDK sends its key as `Authorization: Bearer orqs_...`. We store only the
SHA-256 hash, look the key up to resolve a tenant, and cache the result so the
hot trace path doesn't hit Postgres on every event. When MULTI_TENANT is off
(no DATABASE_URL), everything resolves to the single shared "default" workspace
so local dev keeps working with no auth.
"""

import hashlib
import secrets
import time
import uuid
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import func, select, update

from .. import config

SINGLE_TENANT_ID = "default"
_KEY_PREFIX = "orqs_"
_CACHE_TTL_SECONDS = 300

# key_hash -> (tenant_id, expiry_epoch). Keeps the trace path off the DB.
_key_cache: dict[str, tuple[str, float]] = {}


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Return (plaintext_key, display_prefix). The plaintext is shown once."""
    body = secrets.token_urlsafe(32)
    plaintext = f"{_KEY_PREFIX}{body}"
    return plaintext, plaintext[: len(_KEY_PREFIX) + 4]


def _extract_key(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token.startswith(_KEY_PREFIX):
            return token
    header = request.headers.get("X-Orqis-Key", "").strip()
    return header or None


async def provision_tenant(name: str, github_login: Optional[str] = None) -> tuple[str, str]:
    """Create a tenant + its first API key. Returns (tenant_id, plaintext_key)."""
    from . import db

    tenant_id = uuid.uuid4().hex
    plaintext, prefix = generate_api_key()
    async with db.session() as s:
        s.add(db.Tenant(id=tenant_id, name=name, github_account_login=github_login))
        s.add(
            db.ApiKey(
                id=uuid.uuid4().hex,
                tenant_id=tenant_id,
                key_hash=hash_key(plaintext),
                prefix=prefix,
            )
        )
    return tenant_id, plaintext


async def resolve_tenant_id(plaintext: str) -> Optional[str]:
    """Resolve an API key to a tenant_id, cached for the hot path."""
    key_hash = hash_key(plaintext)
    now = time.time()
    cached = _key_cache.get(key_hash)
    if cached and cached[1] > now:
        return cached[0]

    from . import db

    async with db.session() as s:
        row = (
            await s.execute(select(db.ApiKey).where(db.ApiKey.key_hash == key_hash))
        ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return None
        tenant_id = row.tenant_id
        # Best-effort last-used stamp; never block ingest on it.
        await s.execute(
            update(db.ApiKey).where(db.ApiKey.id == row.id).values(last_used_at=func.now())
        )

    _key_cache[key_hash] = (tenant_id, now + _CACHE_TTL_SECONDS)
    return tenant_id


async def require_tenant(request: Request) -> str:
    """
    FastAPI dependency for ingest endpoints. Returns the resolved tenant_id.
    Single-tenant dev mode returns the shared "default" workspace.
    """
    if not config.MULTI_TENANT:
        return SINGLE_TENANT_ID

    key = _extract_key(request)
    if not key:
        raise HTTPException(status_code=401, detail="missing Orqis API key")
    tenant_id = await resolve_tenant_id(key)
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="invalid or revoked Orqis API key")
    return tenant_id


def invalidate_cache(plaintext: Optional[str] = None) -> None:
    """Drop a cached key (on revocation) or the whole cache."""
    if plaintext is None:
        _key_cache.clear()
    else:
        _key_cache.pop(hash_key(plaintext), None)
