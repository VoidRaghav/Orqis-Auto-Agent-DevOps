"""
In-product GitHub App registration via the manifest flow.

Credentials are persisted under secrets/ (local/self-hosted) and loaded into
runtime config so the server can use the new app without restart.
"""

from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path
from typing import Any, Optional

import httpx

from ... import config

ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = ROOT / "secrets"
STATUS_PATH = SECRETS_DIR / "app_setup_status.json"
ENV_PATH = SECRETS_DIR / "orqis-github-app.env"
PEM_PATH = SECRETS_DIR / "orqis-github-app.pem"


def _public_base() -> str:
    return config.PUBLIC_URL.rstrip("/")


def _webhook_active() -> bool:
    base = _public_base()
    return base.startswith("https://") and "localhost" not in base and "127.0.0.1" not in base


def build_manifest(app_name: Optional[str] = None) -> dict[str, Any]:
    base = _public_base()
    name = app_name or f"Orqis {secrets.token_hex(2)}"
    manifest: dict[str, Any] = {
        "name": name,
        "url": base,
        "redirect_url": f"{base}/integrations/github/register/callback",
        "setup_url": f"{base}/integrations/github/callback",
        "callback_urls": [f"{base}/integrations/github/callback"],
        "setup_on_update": True,
        "public": False,
        "default_permissions": {
            "contents": "write",
            "metadata": "read",
            "pull_requests": "write",
        },
        "default_events": ["installation", "installation_repositories", "pull_request"],
    }
    if _webhook_active():
        manifest["hook_attributes"] = {
            "url": f"{base}/integrations/github/webhook",
            "active": True,
        }
    else:
        manifest["hook_attributes"] = {"active": False}
    return manifest


def register_url(manifest: dict[str, Any], state: str = "orqis-register") -> str:
    raw = json.dumps(manifest, separators=(",", ":"))
    manifest_b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"https://github.com/settings/apps/new?state={state}&manifest={manifest_b64}"


async def convert_manifest(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            f"https://api.github.com/app-manifests/{code}/conversions",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return resp.json()


def apply_runtime_credentials(data: dict[str, Any]) -> dict[str, Any]:
    """Persist PEM + env file and hot-load into config."""
    SECRETS_DIR.mkdir(exist_ok=True)
    app_id = data["id"]
    slug = data["slug"]
    pem = data.get("pem") or ""
    webhook_secret = data.get("webhook_secret") or ""

    PEM_PATH.write_text(pem, encoding="utf-8")
    env_lines = [
        f"GITHUB_APP_ID={app_id}",
        f"GITHUB_APP_SLUG={slug}",
        f"GITHUB_APP_PRIVATE_KEY_PATH={PEM_PATH}",
        f"GITHUB_WEBHOOK_SECRET={webhook_secret}",
        f"ORQIS_PUBLIC_URL={_public_base()}",
    ]
    ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    config.GITHUB_APP_ID = str(app_id)
    config.GITHUB_APP_SLUG = slug
    config.GITHUB_APP_PRIVATE_KEY = ""
    config.GITHUB_APP_PRIVATE_KEY_PATH = str(PEM_PATH)
    if webhook_secret:
        config.GITHUB_WEBHOOK_SECRET = webhook_secret

    status = {
        "state": "done",
        "app_id": app_id,
        "slug": slug,
        "html_url": data.get("html_url"),
        "install_url": f"https://github.com/apps/{slug}/installations/new",
        "webhook_active": _webhook_active(),
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def read_status() -> dict[str, Any]:
    if not STATUS_PATH.is_file():
        return {"state": "idle"}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"state": "idle"}


def registration_allowed() -> bool:
    """Allow manifest registration when app not yet configured."""
    from . import auth

    if auth.is_configured():
        return False
    if config.HOSTED and not config.DEV_MODE:
        return False
    return True
