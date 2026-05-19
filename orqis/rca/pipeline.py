"""
RCA pipeline orchestrator.

Called whenever an error event has a resolvable traceback. Runs the full
detect → locate → patch sequence and persists each state transition so the
dashboard can render progress in real time.

State machine:
  OPEN  →  (file_reader succeeds)  →  OPEN with location set
        →  (patch_generator returns diff)  →  PATCHED
        →  (no diff / no traceback)  →  stays OPEN (interpretation only)

Deduplication:
  Same error fingerprint (first 200 chars of error_message) within
  DEDUP_WINDOW_SECONDS reuses the existing incident and bumps its hit count.
  This prevents 100 identical loop errors from creating 100 incidents.
"""

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

from ..backend import store, ws_manager
from ..backend.models import ErrorType, Incident, IncidentStatus
from ..daemon.interpreter import fallback, interpret
from ..rca import file_reader, patch_generator

# How long (seconds) an incident fingerprint blocks duplicate RCA runs
DEDUP_WINDOW_SECONDS = 300  # 5 minutes

# fingerprint -> (incident_id, created_at_unix_ts)
_recent: dict[str, tuple[str, float]] = {}


def _fingerprint(error_message: str) -> str:
    """Stable key for deduplication — first 200 chars normalised."""
    key = error_message.strip()[:200].lower()
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


def _dedup_lookup(fp: str) -> Optional[str]:
    """Return the incident_id if this fingerprint is still within the window."""
    entry = _recent.get(fp)
    if entry is None:
        return None
    iid, ts = entry
    if (datetime.now(timezone.utc).timestamp() - ts) < DEDUP_WINDOW_SECONDS:
        return iid
    del _recent[fp]
    return None


async def trigger(
    source_event_id: str,
    error_message: str,
    error_type: Optional[ErrorType],
    source: str,
    project_root: Optional[str] = None,
) -> Optional[Incident]:
    """
    Entry point for the RCA pipeline.

    Deduplicates within DEDUP_WINDOW_SECONDS — repeated identical errors bump
    the hit count on the existing incident rather than creating a new one.
    Never raises — failures degrade gracefully to interpretation-only.
    """
    root = project_root or os.getcwd()
    fp = _fingerprint(error_message)

    # --- Deduplication check ---
    existing_id = _dedup_lookup(fp)
    if existing_id:
        existing = await store.get_incident(existing_id)
        if existing and existing.status not in (
            IncidentStatus.APPROVED,
            IncidentStatus.DISMISSED,
        ):
            # Bump hit count and broadcast the update
            hit_count = (existing.hit_count or 1) + 1
            updated = await store.update_incident(existing_id, hit_count=hit_count)
            if updated:
                await _broadcast("incident.updated", updated)
            return existing

    # --- New incident ---
    incident = Incident(
        created_at=datetime.now(timezone.utc),
        status=IncidentStatus.OPEN,
        source_event_id=source_event_id,
        error_type=error_type,
        error_message=error_message,
        interpretation=fallback(error_type),
        source=source,
        hit_count=1,
    )
    await store.save_incident(incident)
    _recent[fp] = (incident.id, incident.created_at.timestamp())
    await _broadcast("incident.created", incident)

    # LLM interpretation runs async — replaces fallback when ready
    asyncio.create_task(
        _update_interpretation(incident.id, error_message, error_type)
    )

    # Locate failing code in traceback
    location = file_reader.extract(error_message, project_root=root)
    if location is None:
        return incident

    incident = await store.update_incident(
        incident.id,
        file_path=location.file_path,
        error_line=location.line,
        function_name=location.function_name,
        code_context=location.context,
        context_start_line=location.context_start_line,
    )
    await _broadcast("incident.located", incident)

    # Generate unified diff patch
    diff = await patch_generator.generate(error_message, location)
    if diff is None:
        return incident

    incident = await store.update_incident(
        incident.id,
        diff=diff,
        status=IncidentStatus.PATCHED.value,
    )
    await _broadcast("incident.patched", incident)
    return incident


async def _update_interpretation(
    incident_id: str,
    error_message: str,
    error_type: Optional[ErrorType],
) -> None:
    text = await interpret(error_message, error_type)
    updated = await store.update_incident(incident_id, interpretation=text)
    if updated:
        await _broadcast("incident.interpretation", updated)


async def _broadcast(event_type: str, incident: Optional[Incident]) -> None:
    if incident is None:
        return
    await ws_manager.manager.broadcast(
        event_type, incident.model_dump(mode="json")
    )
