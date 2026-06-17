"""HTTP helpers for the Orqis MCP server — shared auth header logic."""

from typing import Optional

import httpx


def admin_headers(admin_token: str) -> dict[str, str]:
    if admin_token:
        return {"X-Orqis-Admin-Token": admin_token}
    return {}


def get_json(
    backend: str, path: str, *, params: Optional[dict] = None, timeout: float = 10.0
) -> httpx.Response:
    return httpx.get(f"{backend}{path}", params=params, timeout=timeout)


def post_json(
    backend: str,
    path: str,
    *,
    admin_token: str = "",
    params: Optional[dict] = None,
    timeout: float = 15.0,
) -> httpx.Response:
    return httpx.post(
        f"{backend}{path}",
        params=params,
        headers=admin_headers(admin_token),
        timeout=timeout,
    )
