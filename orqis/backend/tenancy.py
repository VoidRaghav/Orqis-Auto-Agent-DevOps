"""
Workspace (tenant) context for multi-tenant isolation.

When ORQIS_MULTI_TENANT=0 (default), every operation uses workspace ``default``
so local single-tenant workflows stay unchanged.

When ORQIS_MULTI_TENANT=1, ingest and dashboard routes must resolve a workspace
before touching store data.
"""

from __future__ import annotations

import contextvars
from typing import Optional

from .. import config

DEFAULT_WORKSPACE_ID = "default"

_current_workspace: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "orqis_workspace_id", default=None
)


def multi_tenant_enabled() -> bool:
    return config.MULTI_TENANT


def tenant_prefix(workspace_id: Optional[str] = None) -> str:
    """Redis key prefix for the active or explicit workspace."""
    wid = workspace_id or get_workspace_id()
    return f"orqis:t:{wid}:"


def get_workspace_id() -> str:
    """Return the active workspace id (never unset — falls back to default)."""
    wid = _current_workspace.get()
    return wid if wid else DEFAULT_WORKSPACE_ID


def set_workspace_id(workspace_id: str) -> contextvars.Token:
    return _current_workspace.set(workspace_id)


def reset_workspace_id(token: contextvars.Token) -> None:
    _current_workspace.reset(token)


def require_workspace_id() -> str:
    """Fail closed in multi-tenant mode when no workspace is bound."""
    wid = _current_workspace.get()
    if wid:
        return wid
    if multi_tenant_enabled():
        raise RuntimeError("workspace context is required but unset")
    return DEFAULT_WORKSPACE_ID


async def run_in_workspace(workspace_id: str, coro):
    """Run an async coroutine with workspace context (for background tasks)."""
    token = set_workspace_id(workspace_id)
    try:
        return await coro
    finally:
        reset_workspace_id(token)
