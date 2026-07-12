"""Fire-and-forget workspace notifications (webhook + Slack)."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from ..backend import store
from ..backend.models import Incident
from ..backend.tenancy import get_workspace_id


def _payload(event: str, incident: Optional[Incident] = None, extra: Optional[dict] = None) -> dict:
    body: dict[str, Any] = {
        "event": event,
        "workspace_id": get_workspace_id(),
    }
    if incident is not None:
        body["incident"] = {
            "id": incident.id,
            "status": incident.status.value,
            "error_message": incident.error_message[:500],
            "repo_full_name": incident.repo_full_name,
            "pr_url": incident.pr_url,
            "confidence": incident.confidence,
        }
    if extra:
        body.update(extra)
    return body


async def _post(url: str, payload: dict, slack: bool = False) -> None:
    if not url:
        return
    try:
        if slack:
            text = f"[Orqis] {payload.get('event')}: {payload.get('incident', {}).get('error_message', '')}"
            data = {"text": text[:3000]}
        else:
            data = payload
        async with httpx.AsyncClient(timeout=10.0) as http:
            await http.post(url, json=data)
    except Exception:
        pass


async def notify(
    event: str,
    incident: Optional[Incident] = None,
    extra: Optional[dict] = None,
) -> None:
    settings = await store.get_settings()
    webhook = settings.get("notification_webhook_url") or ""
    slack = settings.get("notification_slack_url") or ""
    payload = _payload(event, incident, extra)
    await asyncio.gather(
        _post(webhook, payload),
        _post(slack, payload, slack=True),
    )


async def send_test() -> bool:
    settings = await store.get_settings()
    webhook = settings.get("notification_webhook_url") or ""
    slack = settings.get("notification_slack_url") or ""
    if not webhook and not slack:
        return False
    payload = _payload("test", extra={"message": "Orqis notification test"})
    await notify("test", extra={"message": "Orqis notification test"})
    return True
