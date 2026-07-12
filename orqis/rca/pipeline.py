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
import re
import sys
from datetime import datetime, timezone
from typing import Optional

from ..backend.tenancy import get_workspace_id, reset_workspace_id, set_workspace_id
from ..backend.models import ErrorType, Incident, IncidentStatus, ValidationStatus
from ..daemon.interpreter import fallback, interpret
from ..integrations.github import auth as gh_auth
from ..integrations.github import pr_service
from ..rca import (
    confidence,
    file_reader,
    patch_generator,
    remediation,
    source_resolver,
    validator,
)

# How long (seconds) an incident fingerprint blocks duplicate RCA runs
DEDUP_WINDOW_SECONDS = 300  # 5 minutes

# Statuses that should NOT collapse a fresh error into the existing incident —
# the prior incident is finished, so a recurrence is a genuinely new one (I4).
_TERMINAL_FOR_DEDUP = (
    IncidentStatus.APPROVED,
    IncidentStatus.DISMISSED,
    IncidentStatus.RESOLVED,
)

# Serialises concurrent fingerprint check-and-set so two simultaneous triggers
# for the same error can't both miss the dedup table and create twin incidents.
_dedup_lock = asyncio.Lock()


def _spawn(coro, workspace_id: Optional[str] = None):
    """Run async work in a detached task with workspace context preserved."""
    wid = workspace_id or get_workspace_id()

    async def _wrapped():
        token = set_workspace_id(wid)
        try:
            await coro
        finally:
            reset_workspace_id(token)

    return asyncio.create_task(_wrapped())


def _fingerprint(error_message: str, error_type: Optional[ErrorType] = None) -> str:
    """Stable key — structural frame + error type + message prefix."""
    parts: list[str] = []
    if error_type is not None:
        parts.append(error_type.value)
    frames = file_reader.parse_frames(error_message)
    if frames:
        path, line = frames[-1]
        parts.append(f"{path}:{line}")
    parts.append(error_message.strip()[:200].lower())
    key = "|".join(parts)
    return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


async def _dedup_bump(fp: str) -> Optional[Incident]:
    """
    If this fingerprint maps to a still-active incident, bump its hit count and
    return it (caller should short-circuit). Returns None when there's no live
    incident to collapse into and a new one should be created (I4).
    """
    existing_id = await store.dedup_get(fp)
    if not existing_id:
        return None
    existing = await store.get_incident(existing_id)
    if existing is None or existing.status in _TERMINAL_FOR_DEDUP:
        return None
    hit_count = (existing.hit_count or 1) + 1
    updated = await store.update_incident(existing_id, hit_count=hit_count)
    if updated:
        await _broadcast("incident.updated", updated)
    return existing


async def _locate(error_message: str, source: str, root: str):
    """
    Locate the failing code. Tries the GitHub repo first (works on a server with
    no local checkout); falls back to the local filesystem for dev. Returns
    (location, resolved) where resolved is a ResolvedSource or None.
    """
    resolved = await source_resolver.resolve(error_message, source)
    if resolved is not None:
        return resolved.location, resolved
    location = file_reader.extract(error_message, project_root=root)
    return location, None


def _located_fields(location, resolved) -> dict:
    """Build the incident update dict for a located code position."""
    fields = dict(
        file_path=location.file_path,
        error_line=location.line,
        function_name=location.function_name,
        code_context=location.context,
        context_start_line=location.context_start_line,
        repo_relative_path=location.repo_relative_path,
    )
    if resolved is not None:
        fields.update(
            repo_full_name=resolved.repo_full_name,
            base_branch=resolved.base_branch,
            base_sha=resolved.base_sha,
        )
    return fields


async def _attach_repo_from_settings(
    incident: Incident, source: str, location, resolved
) -> Incident:
    if resolved is not None or incident.repo_full_name:
        return incident
    import os

    settings = await store.get_settings()
    repo = source_resolver.repo_for_source(settings, source)
    if not repo:
        return incident
    rel = location.repo_relative_path
    if not rel and location.file_path and config.PROJECT_ROOT:
        try:
            rel = os.path.relpath(location.file_path, config.PROJECT_ROOT).replace("\\", "/")
        except ValueError:
            rel = None
    if not rel:
        return incident
    updated = await store.update_incident(
        incident.id, repo_full_name=repo, repo_relative_path=rel
    )
    return updated or incident


async def _finalize_patch(
    incident: Incident, diff: str, location, fix_method: str
) -> Incident:
    """
    Validate the diff, score confidence, persist the patch, broadcast, and
    schedule an auto-PR when eligible. Deterministic fixes get a confidence
    floor so a correct-by-construction libcst patch is never demoted (R3).
    """
    result = await validator.validate(
        diff, location.file_path, source_text=location.source_text
    )
    conf = confidence.score(diff, location, result)

    if result.valid and (fix_method == "deterministic" or conf >= confidence.THRESHOLD):
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
        fix_method=fix_method,
        validation_errors=result.errors,
        validation_warnings=result.warnings,
    )
    await _broadcast("incident.patched", incident)
    await _maybe_open_pr(incident)
    if incident.status in (IncidentStatus.PATCHED, IncidentStatus.LOW_CONFIDENCE):
        from ..notifications import dispatcher

        _spawn(dispatcher.notify("incident.patched", incident))
    return incident


async def _maybe_open_pr(incident: Optional[Incident]) -> None:
    """
    Schedule an async auto-PR when the incident is PATCHED, mapped to a GitHub
    repo, and the app is configured. LOW_CONFIDENCE only auto-PRs when the
    workspace opted in via pr_low_confidence (S1).
    """
    if incident is None or not incident.repo_full_name:
        return
    if not gh_auth.is_configured():
        return

    if incident.status == IncidentStatus.PATCHED:
        _spawn(pr_service.open_fix_pr(incident))
        return

    if incident.status == IncidentStatus.LOW_CONFIDENCE:
        settings = await store.get_settings()
        if settings.get("pr_low_confidence"):
            _spawn(pr_service.open_fix_pr(incident))


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
    fp = _fingerprint(error_message, error_type)

    # --- Atomic dedup check-and-create -------------------------------------
    # Hold the lock across the lookup AND the new-incident save so two
    # concurrent triggers for the same fingerprint can't both miss the
    # table and create twin incidents. Dedup state lives in Redis (P5) so it
    # survives restarts and is shared across workers.
    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
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
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    # LLM interpretation runs async — replaces fallback when ready
    _spawn(_update_interpretation(incident.id, error_message, error_type))

    # Locate failing code — GitHub repo first (server), local disk as fallback.
    location, resolved = await _locate(error_message, source, root)
    if location is None:
        print(
            f"\033[33m[orqis] could not locate source for incident "
            f"{incident.id} — checked GitHub repo + project_root={root}\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Generate unified diff patch
    diff = await patch_generator.generate(error_message, location)
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method="llm")


async def trigger_anomaly(signal) -> Optional[Incident]:
    """
    Entry point for behavioural anomalies (runaway tool loops) detected on the
    live trace stream. Unlike trigger(), there is no traceback — the detector
    already knows the looping call site, so we locate it directly.

    signal is an anomaly.AnomalySignal. Never raises.
    """
    fp = _fingerprint(message, ErrorType.RUNAWAY_LOOP)
    args = f"({signal.tool_args})" if signal.tool_args else "()"
    message = (
        f"Runaway tool loop: {signal.tool_name}{args} called "
        f"{signal.call_count} times in under {signal.window_seconds:.0f}s with no "
        f"exit condition. ${signal.cost_usd:.2f} burned, 0 tasks completed."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
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
            # Money this fix recovers — surfaced in the PR title (A8).
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    # GitHub repo first (server path), then local disk (dev).
    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] runaway loop located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    fields = _located_fields(location, resolved)
    incident = await store.update_incident(incident.id, **fields)
    incident = await _attach_repo_from_settings(incident, signal.source, location, resolved)
    await _broadcast("incident.located", incident)

    # Known failure class: apply the verified bounded-retry remediation first.
    # Fall back to the LLM only if the loop shape isn't one we can template.
    diff = remediation.guard_runaway_loop(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="loop")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


def _parse_code_location(loc: Optional[str]) -> tuple[Optional[str], int]:
    """
    Split a 'file:line:function' marker into (file_path, line).

    Parses the trailing ':line' (with an optional ':function' after it) from the
    right so the file portion is preserved intact — including Windows drive
    colons (C:\\...) and any other colons in the path.
    """
    if not loc:
        return None, 0
    m = re.search(r":(\d+)(?::[^:]*)?$", loc)
    if not m:
        return None, 0
    return loc[: m.start()], int(m.group(1))


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
        event_type,
        incident.model_dump(mode="json"),
        workspace_id=get_workspace_id(),
    )
