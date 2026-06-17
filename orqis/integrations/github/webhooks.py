"""
GitHub webhook handling.

Verifies the X-Hub-Signature-256 HMAC, dedups deliveries by GUID (S6), and
dispatches the two events the fix flow cares about:

  installation / installation_repositories
      -> refresh stored installation_id + accessible repo list

  pull_request (closed + merged)
      -> resolve the matching incident, clean up, hot-reload (step 5)

Also exposes poll_open_prs() — a safety net that reconciles incidents stuck in
pr_open when a webhook was missed or misconfigured (U1/P4).
"""

import hashlib
import hmac
from typing import Optional

from ... import config
from ...backend import store
from ...backend.models import IncidentStatus
from . import auth, client, pr_service


def verify_signature(body: bytes, signature: Optional[str], secret: str) -> bool:
    """Verify GitHub's HMAC-SHA256 delivery signature (constant-time)."""
    if not secret:
        return config.DEV_MODE  # open only in local dev (C3)
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


async def _handle_installation(payload: dict) -> dict:
    """Persist/refresh the installation id + accessible repos."""
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    if not installation_id:
        return {"ok": False, "reason": "no installation id"}

    action = payload.get("action")
    if action in ("deleted", "suspend"):
        await store.save_settings({"installation_id": None, "repos": []})
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
    from ...backend import ws_manager

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
    )
    return {"ok": True, "installation_id": installation_id, "repos": len(repos)}


async def _handle_pull_request(payload: dict) -> dict:
    """Resolve the incident when its fix PR is merged."""
    if payload.get("action") != "closed":
        return {"ok": True, "ignored": "pr not closed"}

    pr = payload.get("pull_request") or {}
    if not pr.get("merged"):
        return {"ok": True, "ignored": "pr closed without merge"}

    repo = (payload.get("repository") or {}).get("full_name")
    pr_number = pr.get("number")
    if not repo or pr_number is None:
        return {"ok": False, "reason": "missing repo/pr_number"}

    incident_id = await store.get_incident_id_by_pr(repo, pr_number)
    if not incident_id:
        # Race: index not written yet (P4) — the poll fallback will catch it.
        return {"ok": True, "pending": "no incident index yet"}

    merge_sha = pr.get("merge_commit_sha")
    resolved = await pr_service.mark_resolved(incident_id, repo, pr_number, merge_sha)
    return {"ok": True, "resolved": bool(resolved)}


async def poll_open_prs() -> int:
    """
    Reconcile incidents stuck in pr_open by polling GitHub directly. Resolves any
    whose PR has since merged. Returns the number newly resolved. Safe to call on
    a timer; never raises.
    """
    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        return 0

    # Scan a generous window so we don't miss older open PRs (paging — polish).
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
