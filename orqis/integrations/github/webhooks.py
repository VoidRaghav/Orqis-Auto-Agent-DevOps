"""
GitHub webhook handling — routes installations to the correct workspace.
"""

import hashlib
import hmac
from typing import Optional

from ... import config
from ...backend import store, ws_manager, tenancy, workspace_auth
from ...backend.models import IncidentStatus
from . import auth, client, pr_service


def verify_signature(body: bytes, signature: Optional[str], secret: str) -> bool:
    """Verify GitHub's HMAC-SHA256 delivery signature (constant-time)."""
    if not secret:
        return config.DEV_MODE
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle(event: str, payload: dict) -> dict:
    """Dispatch a verified webhook payload. Never raises."""
    if event in ("installation", "installation_repositories"):
        return await _handle_installation(payload)
    if event == "pull_request":
        return await _handle_pull_request(payload)
    return {"ok": True, "ignored": event}


async def _with_workspace(workspace_id: str, coro):
    token = tenancy.set_workspace_id(workspace_id)
    try:
        return await coro
    finally:
        tenancy.reset_workspace_id(token)


async def _handle_installation(payload: dict) -> dict:
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    if not installation_id:
        return {"ok": False, "reason": "no installation id"}

    workspace_id = await workspace_auth.get_workspace_for_installation(installation_id)
    if not workspace_id:
        # Installation not yet bound via OAuth callback — ignore until user completes flow
        return {"ok": True, "pending": "installation not bound to workspace"}

    action = payload.get("action")

    async def _run():
        if action in ("deleted", "suspend"):
            await store.save_settings({"installation_id": None, "repos": []})
            await workspace_auth.clear_install_workspace(installation_id)
            return {"ok": True, "action": action}

        account = installation.get("account") or {}
        repos = await auth.list_installation_repos(installation_id)
        await store.save_settings(
            {
                "installation_id": installation_id,
                "account_login": account.get("login"),
                "repos": repos,
            }
        )
        settings = await store.get_settings()
        await ws_manager.manager.broadcast(
            "settings.updated",
            {
                "configured": bool(auth.is_configured()),
                "install_url": "",
                "connected": bool(settings.get("installation_id")),
                "account_login": settings.get("account_login"),
                "repos": settings.get("repos", []),
            },
            workspace_id=workspace_id,
        )
        return {"ok": True, "installation_id": installation_id, "repos": len(repos)}

    return await _with_workspace(workspace_id, _run())


async def _handle_pull_request(payload: dict) -> dict:
    if payload.get("action") != "closed":
        return {"ok": True, "ignored": "pr not closed"}

    pr = payload.get("pull_request") or {}
    if not pr.get("merged"):
        return {"ok": True, "ignored": "pr closed without merge"}

    repo = (payload.get("repository") or {}).get("full_name")
    pr_number = pr.get("number")
    if not repo or pr_number is None:
        return {"ok": False, "reason": "missing repo/pr_number"}

    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    workspace_id = None
    if installation_id:
        workspace_id = await workspace_auth.get_workspace_for_installation(installation_id)

    async def _run():
        incident_id = await store.get_incident_id_by_pr(repo, pr_number)
        if not incident_id:
            return {"ok": True, "pending": "no incident index yet"}
        merge_sha = pr.get("merge_commit_sha")
        resolved = await pr_service.mark_resolved(incident_id, repo, pr_number, merge_sha)
        return {"ok": True, "resolved": bool(resolved)}

    if workspace_id:
        return await _with_workspace(workspace_id, _run())
    return {"ok": True, "pending": "installation not bound to workspace"}


async def poll_open_prs() -> int:
    """Reconcile pr_open incidents per workspace installation."""
    if not config.MULTI_TENANT:
        return await _poll_for_workspace()

    r = await store.get_redis()
    install_keys = await store.scan_keys("orqis:install:*")
    total = 0
    for key in install_keys:
        wid = await r.get(key)
        if wid:
            total += await _with_workspace(wid, _poll_for_workspace())
    return total


async def _poll_for_workspace() -> int:
    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        return 0

    incidents = await store.get_recent_incidents(limit=200)
    resolved = 0
    for incident in incidents:
        if incident.status != IncidentStatus.PR_OPEN:
            continue
        if not incident.repo_full_name or incident.pr_number is None:
            continue
        pr = await client.get_pull_request(
            installation_id, incident.repo_full_name, incident.pr_number
        )
        if pr is None:
            continue
        if pr.get("merged"):
            await pr_service.mark_resolved(
                incident.id,
                incident.repo_full_name,
                incident.pr_number,
                pr.get("merge_commit_sha"),
            )
            resolved += 1
    return resolved
