"""
Change log — the audit trail of every change Orqis makes.

A single entry is recorded (and pushed live to the dashboard "CHANGES" feed)
whenever Orqis applies a fix to the local working copy, opens a fix PR, a PR
merges, or an incident is dismissed. This is the user-facing record of "what
did Orqis actually change", separate from the incident list.
"""

from datetime import datetime, timezone
from typing import Optional

from . import store, ws_manager
from .models import ChangeLogEntry, Incident
from .tenancy import get_workspace_id


def _short_path(incident: Incident) -> Optional[str]:
    """Prefer the repo-relative path; fall back to the basename of file_path."""
    if incident.repo_relative_path:
        return incident.repo_relative_path
    if incident.file_path:
        # Normalise separators and show the last two path segments for context.
        parts = incident.file_path.replace("\\", "/").rstrip("/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    return None


async def record(
    action: str,
    incident: Incident,
    summary: str,
    *,
    applied_locally: bool = False,
    local_path: Optional[str] = None,
) -> ChangeLogEntry:
    """Persist a change-log entry and broadcast it to the dashboard."""
    entry = ChangeLogEntry(
        timestamp=datetime.now(timezone.utc),
        action=action,
        incident_id=incident.id,
        summary=summary,
        file=_short_path(incident),
        applied_locally=applied_locally,
        local_path=local_path,
        repo_full_name=incident.repo_full_name,
        pr_url=incident.pr_url,
        pr_number=incident.pr_number,
        error_type=incident.error_type,
        diff=incident.diff,
    )
    await store.save_change(entry)
    await ws_manager.manager.broadcast(
        "change.logged", entry.model_dump(mode="json"), workspace_id=get_workspace_id()
    )
    return entry
