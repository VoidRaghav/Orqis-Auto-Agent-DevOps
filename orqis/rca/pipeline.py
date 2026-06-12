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
import sys
from datetime import datetime, timezone
from typing import Optional

from .. import config
from ..backend import store, ws_manager
from ..backend.models import ErrorType, Incident, IncidentStatus, ValidationStatus
from ..daemon.interpreter import fallback, interpret
from ..rca import confidence, file_reader, patch_generator, remediation, validator

# How long (seconds) an incident fingerprint blocks duplicate RCA runs
DEDUP_WINDOW_SECONDS = 300  # 5 minutes

# fingerprint -> (incident_id, created_at_unix_ts)
_recent: dict[str, tuple[str, float]] = {}

# Serialises concurrent fingerprint check-and-set so two simultaneous triggers
# for the same error can't both miss the dedup table and create twin incidents.
_dedup_lock = asyncio.Lock()


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
    root = project_root or config.PROJECT_ROOT
    fp = _fingerprint(error_message)

    # --- Atomic dedup check-and-create -------------------------------------
    # Hold the lock across the lookup AND the new-incident save so two
    # concurrent triggers for the same fingerprint can't both miss the
    # table and create twin incidents.
    async with _dedup_lock:
        existing_id = _dedup_lookup(fp)
        if existing_id:
            existing = await store.get_incident(existing_id)
            if existing and existing.status not in (
                IncidentStatus.APPROVED,
                IncidentStatus.DISMISSED,
            ):
                hit_count = (existing.hit_count or 1) + 1
                updated = await store.update_incident(existing_id, hit_count=hit_count)
                if updated:
                    await _broadcast("incident.updated", updated)
                return existing

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
        print(
            f"\033[33m[orqis] could not locate source for incident "
            f"{incident.id} — checked under project_root={root}\033[0m",
            file=sys.stderr,
        )
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

    # Run verification gates before exposing the patch
    result = await validator.validate(diff, location.file_path)
    conf = confidence.score(diff, location, result)

    if result.valid and conf >= confidence.THRESHOLD:
        status  = IncidentStatus.PATCHED.value
        vstatus = ValidationStatus.PASSED.value
    elif result.valid:
        status  = IncidentStatus.LOW_CONFIDENCE.value
        vstatus = ValidationStatus.LOW_CONFIDENCE.value
    else:
        status  = IncidentStatus.LOW_CONFIDENCE.value
        vstatus = ValidationStatus.FAILED.value

    incident = await store.update_incident(
        incident.id,
        diff=diff,
        status=status,
        validation_status=vstatus,
        confidence=conf,
        validation_errors=result.errors,
        validation_warnings=result.warnings,
    )
    await _broadcast("incident.patched", incident)
    return incident


async def trigger_anomaly(signal) -> Optional[Incident]:
    """
    Entry point for behavioural anomalies (runaway tool loops) detected on the
    live trace stream. Unlike trigger(), there is no traceback — the detector
    already knows the looping call site, so we locate it directly.

    signal is an anomaly.AnomalySignal. Never raises.
    """
    fp = _fingerprint(f"loop:{signal.source}:{signal.tool_name}:{signal.tool_args}")
    args = f"({signal.tool_args})" if signal.tool_args else "()"
    message = (
        f"Runaway tool loop: {signal.tool_name}{args} called "
        f"{signal.call_count} times in under {signal.window_seconds:.0f}s with no "
        f"exit condition. ${signal.cost_usd:.2f} burned, 0 tasks completed."
    )

    async with _dedup_lock:
        existing_id = _dedup_lookup(fp)
        if existing_id:
            existing = await store.get_incident(existing_id)
            if existing and existing.status not in (
                IncidentStatus.APPROVED,
                IncidentStatus.DISMISSED,
            ):
                hit_count = (existing.hit_count or 1) + 1
                updated = await store.update_incident(existing_id, hit_count=hit_count)
                if updated:
                    await _broadcast("incident.updated", updated)
                return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.RUNAWAY_LOOP,
            error_message=message,
            interpretation=fallback(ErrorType.RUNAWAY_LOOP),
            source=signal.source,
            hit_count=1,
        )
        await store.save_incident(incident)
        _recent[fp] = (incident.id, incident.created_at.timestamp())

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] runaway loop located at {signal.code_location} but "
            f"source unreadable under project_root={config.PROJECT_ROOT}\033[0m",
            file=sys.stderr,
        )
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

    # Known failure class: apply the verified bounded-retry remediation first.
    # Fall back to the LLM only if the loop shape isn't one we can template.
    diff = remediation.guard_runaway_loop(location)
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="loop")
    if diff is None:
        return incident

    result = await validator.validate(diff, location.file_path)
    conf = confidence.score(diff, location, result)

    if result.valid and conf >= confidence.THRESHOLD:
        status, vstatus = IncidentStatus.PATCHED.value, ValidationStatus.PASSED.value
    elif result.valid:
        status, vstatus = IncidentStatus.LOW_CONFIDENCE.value, ValidationStatus.LOW_CONFIDENCE.value
    else:
        status, vstatus = IncidentStatus.LOW_CONFIDENCE.value, ValidationStatus.FAILED.value

    incident = await store.update_incident(
        incident.id,
        diff=diff,
        status=status,
        validation_status=vstatus,
        confidence=conf,
        validation_errors=result.errors,
        validation_warnings=result.warnings,
    )
    await _broadcast("incident.patched", incident)
    return incident


def _parse_code_location(loc: Optional[str]) -> tuple[Optional[str], int]:
    """Split a 'file.py:line:function' marker into (file_path, line)."""
    if not loc:
        return None, 0
    parts = loc.split(":")
    if len(parts) < 2:
        return None, 0
    try:
        return parts[0], int(parts[1])
    except ValueError:
        return None, 0


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
