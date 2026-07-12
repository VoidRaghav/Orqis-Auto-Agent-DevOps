"""HTTP helpers for the Orqis MCP server — shared auth header logic."""

import os
from typing import Optional

import httpx


def _auth_headers(admin_token: str = "", api_key: str = "") -> dict[str, str]:
    """Prefer workspace API key (hosted); fall back to admin token (local)."""
    key = api_key or os.getenv("ORQIS_API_KEY", "")
    if key:
        return {"Authorization": f"Bearer {key}"}
    if admin_token:
        return {"X-Orqis-Admin-Token": admin_token}
    return {}


def admin_headers(admin_token: str) -> dict[str, str]:
    return _auth_headers(admin_token=admin_token)


def get_json(
    backend: str,
    path: str,
    *,
    admin_token: str = "",
    api_key: str = "",
    params: Optional[dict] = None,
    timeout: float = 10.0,
) -> httpx.Response:
    return httpx.get(
        f"{backend}{path}",
        params=params,
        headers=_auth_headers(admin_token, api_key),
        timeout=timeout,
    )


def post_json(
    backend: str,
    path: str,
    *,
    admin_token: str = "",
    api_key: str = "",
    params: Optional[dict] = None,
    timeout: float = 15.0,
) -> httpx.Response:
    return httpx.post(
        f"{backend}{path}",
        params=params,
        headers=_auth_headers(admin_token, api_key),
        timeout=timeout,
    )
