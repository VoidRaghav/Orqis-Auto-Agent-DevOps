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

from .. import config
from ..backend import store, ws_manager
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

    # A deterministic libcst transform is a verified template — correct by
    # construction. Once it passes validation, don't let the heuristic score
    # demote it just because the change landed a few lines off the anchor (R3).
    if fix_method == "deterministic" and result.valid:
        conf = 100

    if result.valid and (fix_method == "deterministic" or conf >= confidence.THRESHOLD):
        status, vstatus = IncidentStatus.PATCHED.value, ValidationStatus.PASSED.value
    elif result.valid:
        status, vstatus = IncidentStatus.LOW_CONFIDENCE.value, ValidationStatus.LOW_CONFIDENCE.value
    else:
        status, vstatus = IncidentStatus.LOW_CONFIDENCE.value, ValidationStatus.FAILED.value

    fix_scope = _fix_scope(incident, location, fix_method)

    incident = await store.update_incident(
        incident.id,
        diff=diff,
        status=status,
        validation_status=vstatus,
        confidence=conf,
        fix_method=fix_method,
        fix_scope=fix_scope,
        validation_errors=result.errors,
        validation_warnings=result.warnings,
    )
    await _broadcast("incident.patched", incident)
    await _maybe_open_pr(incident)
    if incident.status in (IncidentStatus.PATCHED, IncidentStatus.LOW_CONFIDENCE):
        from ..notifications import dispatcher

        _spawn(dispatcher.notify("incident.patched", incident))
    return incident


# Distinct code sites seen per (source, error type), so a pattern showing up at
# more than one place reads as systemic — a band-aid guard there is not enough.
_sites_seen: dict[tuple, set] = {}


def reset_fix_router() -> None:
    """Clear the spread tracker (demo reset), so runs start fresh."""
    _sites_seen.clear()


def _fix_scope(incident: Incident, location, fix_method: str) -> str:
    """
    Decide the trust tier from two concrete signals, no severity guessing:
      - a verified deterministic template fitting the bug  -> the fix is a small
        guard (correct by construction),
      - the same failure appearing at only one site         -> local, not systemic.
    Both true -> "guard" (auto-merge safe). Otherwise (an LLM rewrite, or the
    pattern seen at >1 site) -> "structural" (a human reviews it, never auto-merged).
    """
    site = location.repo_relative_path or location.file_path or "?"
    site_key = f"{site}:{location.function_name}"
    seen = _sites_seen.setdefault((incident.source, incident.error_type), set())
    seen.add(site_key)
    systemic = len(seen) > 1
    return "structural" if fix_method == "llm" or systemic else "guard"


async def _maybe_open_pr(incident: Optional[Incident]) -> None:
    """
    Schedule an async auto-PR only for the auto-merge-safe tier: a PATCHED
    incident whose fix is a "guard" (a small, verified, single-site change).
    A "structural" fix (an LLM rewrite, or a systemic pattern) is left as PATCHED
    for a human to open/approve on the dashboard — never auto-merged. A
    LOW_CONFIDENCE fix only auto-PRs when the workspace opted in (S1).
    """
    if incident is None or not incident.repo_full_name:
        return
    if not gh_auth.is_configured():
        return

    if incident.status == IncidentStatus.PATCHED:
        # Only the auto-merge-safe tier auto-opens a PR: a "guard" (small,
        # verified, single-site). A "structural" fix (LLM or systemic) stays
        # PATCHED for a human to open on the dashboard — never auto-merged.
        if incident.fix_scope == "guard":
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
    args = f"({signal.tool_args})" if signal.tool_args else "()"
    message = (
        f"Runaway tool loop: {signal.tool_name}{args} called "
        f"{signal.call_count} times in under {signal.window_seconds:.0f}s with no "
        f"exit condition. ${signal.cost_usd:.2f} burned, 0 tasks completed."
    )
    fp = _fingerprint(message, ErrorType.RUNAWAY_LOOP)

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


async def trigger_corruption(signal) -> Optional[Incident]:
    """
    Entry point for silent tool-call corruption detected on the live trace
    stream: a tool with an established schema started returning empty/degenerate
    payloads that the agent consumed without validating. No traceback — the
    detector already knows the consuming call site. signal is a
    corruption.CorruptionSignal. Never raises.
    """
    fp = _fingerprint(f"corruption:{signal.source}:{signal.tool_name}")
    schema = ", ".join(signal.expected_keys) if signal.expected_keys else "structured data"
    message = (
        f"Silent tool corruption: {signal.tool_name}() returned an empty payload "
        f"{signal.corrupt_count} times after {signal.healthy_count} healthy calls "
        f"(expected {{{schema}}}). The agent consumed it without validating and "
        f"kept going — no exception raised, corrupt context propagating downstream."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.CORRUPT_TOOL_OUTPUT,
            error_message=message,
            interpretation=fallback(ErrorType.CORRUPT_TOOL_OUTPUT),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] corruption located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Known failure class: insert a verified output-validation guard first; fall
    # back to the LLM only if the consuming call site isn't one we can template.
    diff = remediation.guard_corrupt_output(location, signal.tool_name)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="corruption")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_cost_spike(signal) -> Optional[Incident]:
    """
    Entry point for a token/cost spike detected on the live trace stream: an
    agent's per-call tokens climbed far above its own baseline because its
    memory is never trimmed. No traceback — the detector knows the call site.
    signal is a cost_spike.CostSpikeSignal. Never raises.
    """
    fp = _fingerprint(f"cost_spike:{signal.source}")
    message = (
        f"Token/cost spike: per-call input tokens climbed to {signal.peak_tokens:,} "
        f"({signal.factor:.1f}x the {signal.baseline_tokens:,}-token baseline) because "
        f"the agent's memory is never trimmed. No error raised — the bill just inflates."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.COST_SPIKE,
            error_message=message,
            interpretation=fallback(ErrorType.COST_SPIKE),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] cost spike located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Known failure class: cap the unbounded memory in place first; fall back to
    # the LLM only if there is no append-style memory we can template.
    diff = remediation.cap_unbounded_memory(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="cost")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_retry_storm(signal) -> Optional[Incident]:
    """
    Entry point for a silent retry storm detected on the live trace stream: a
    tool was retried past a sane count because a transient failure (timeout /
    429 / 503) is retried with no backoff. No traceback — the detector knows the
    retry site. signal is a retry_storm.RetryStormSignal. Never raises.
    """
    fp = _fingerprint(f"retry_storm:{signal.source}:{signal.tool_name}")
    args = f"({signal.tool_args})" if signal.tool_args else "()"
    message = (
        f"Silent retry storm: {signal.tool_name}{args} failed with {signal.error_type} "
        f"and was retried {signal.retry_count} times with no backoff before succeeding. "
        f"No error raised — the retries bled ${signal.cost_usd:.2f} and hammered the downstream."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.RETRY_STORM,
            error_message=message,
            interpretation=fallback(ErrorType.RETRY_STORM),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] retry storm located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Known failure class: inject exponential backoff into the retry loop first;
    # fall back to the LLM only if there is no for-loop we can template.
    diff = remediation.add_backoff(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="retry")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_binding_drop(signal) -> Optional[Incident]:
    """
    Entry point for a structured-output / tool-binding drop detected on the live
    trace stream: a tool was bound but the chain returned structured output
    without ever invoking it. No traceback — the detector knows the chain site.
    The fix restructures a framework-specific chain, so it is generated by the
    LLM rather than a template. signal is a binding_drop.BindingDropSignal.
    Never raises.
    """
    fp = _fingerprint(f"binding_drop:{signal.source}")
    tools = ", ".join(signal.bound_tools) if signal.bound_tools else "a tool"
    message = (
        f"Tool-binding drop: {tools} was bound but never invoked across "
        f"{signal.drop_count} calls that returned structured output — the model "
        f"fabricated the JSON instead of calling the tool. No error raised; the "
        f"tool's real work never happened."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.TOOL_BINDING_DROP,
            error_message=message,
            interpretation=fallback(ErrorType.TOOL_BINDING_DROP),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] binding drop located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Deterministic first: drop the structured-output wrapper that swallows the
    # tool binding so the tool is invoked again. The LLM fallback can go further
    # (re-add structured parsing on top) for chains we can't template.
    diff = remediation.fix_binding_drop(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="binding")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_pingpong(signal) -> Optional[Incident]:
    """
    Entry point for a multi-agent hand-off ping-pong detected on the live trace
    stream: two agents bounce a task A->B->A->B with no resolver or turn limit.
    No traceback — the detector knows the orchestration loop. The fix bounds that
    loop with a turn limit (the same verified remediation as a runaway loop).
    signal is a pingpong.PingPongSignal. Never raises.
    """
    fp = _fingerprint(f"pingpong:{signal.run_id}:{'/'.join(signal.agents)}")
    pair = " <-> ".join(signal.agents) if signal.agents else "two agents"
    message = (
        f"Multi-agent ping-pong: {pair} handed the task back and forth "
        f"{signal.handoff_count} times with no resolver or turn limit. Neither "
        f"agent is looping alone — the orchestration is — so no per-agent check "
        f"catches it while cost bleeds."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.MULTI_AGENT_PINGPONG,
            error_message=message,
            interpretation=fallback(ErrorType.MULTI_AGENT_PINGPONG),
            source=signal.sources[0] if signal.sources else signal.run_id,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(
        signal.sources[0] if signal.sources else "", file_path, line
    )
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] ping-pong located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # The orchestration loop has no turn limit — the same bounded-loop guard that
    # fixes a runaway loop bounds the hand-off loop here. LLM fallback otherwise.
    diff = remediation.guard_runaway_loop(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="loop")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_overflow(signal) -> Optional[Incident]:
    """
    Entry point for a context-window overflow detected on the live trace stream:
    per-call input tokens sit at/over the model's window, so the prompt is
    silently truncated. No traceback — the detector knows the context site. The
    fix bounds the context so it fits. signal is an overflow.OverflowSignal.
    Never raises.
    """
    fp = _fingerprint(f"overflow:{signal.source}")
    message = (
        f"Context overflow: {signal.peak_tokens:,} input tokens against the "
        f"{signal.window:,}-token window of {signal.model} ({signal.fraction:.0%} "
        f"of the limit). The prompt is silently truncated — usually the system "
        f"instructions — so the agent answers off-policy with no error raised."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.CONTEXT_OVERFLOW,
            error_message=message,
            interpretation=fallback(ErrorType.CONTEXT_OVERFLOW),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] context overflow located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Deterministic first: slice the collection stuffed into the prompt so it
    # fits the window. LLM fallback can add relevance-ranked retrieval instead.
    diff = remediation.cap_context_window(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="context")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_injection(signal) -> Optional[Incident]:
    """
    Entry point for a successful prompt injection detected on the live trace
    stream: an injected input pushed the agent into a tool outside its allowed
    set. No traceback — the detector knows the dispatch site. The guardrail fix
    (an allowlist check) is context-specific, so the LLM patcher writes it.
    signal is an injection.InjectionSignal. Never raises.
    """
    fp = _fingerprint(f"injection:{signal.source}:{signal.tool_name}")
    allowed = ", ".join(signal.allowed_tools) if signal.allowed_tools else "its normal tools"
    message = (
        f"Prompt injection succeeded: the agent called '{signal.tool_name}', outside "
        f"its established set ({allowed}), driven by an injected input "
        f"(\"{signal.snippet}\"). Behaviour diverged with no error raised."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.PROMPT_INJECTION,
            error_message=message,
            interpretation=fallback(ErrorType.PROMPT_INJECTION),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] injection located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # The guardrail (an allowlist check) is agent-specific, so the LLM patcher
    # writes it — through the resilient provider chain, so an outage can't block it.
    diff = await patch_generator.generate(message, location, kind="injection")
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method="llm")


async def trigger_stuck(signal) -> Optional[Incident]:
    """
    Entry point for a stuck / zero-output agent found by the watchdog: an
    operation started and then went silent, waiting on something that never
    resolves. No traceback — the detector knows the waiting site. The fix bounds
    the wait (a max-attempts guard, or a timeout via the LLM). signal is a
    stuck.StuckSignal. Never raises.
    """
    fp = _fingerprint(f"stuck:{signal.source}:{signal.code_location}")
    message = (
        f"Stuck agent: '{signal.operation}' started and then made no progress for "
        f"{signal.seconds_stuck:.0f}s — the agent is waiting on something that never "
        f"resolves. No output, no error; only the silence reveals it."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.AGENT_STUCK,
            error_message=message,
            interpretation=fallback(ErrorType.AGENT_STUCK),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] stuck agent located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # Deterministic first: bound the wait loop with a max-attempts guard (the same
    # verified transform as a runaway loop). LLM timeout fallback otherwise.
    diff = remediation.guard_runaway_loop(location)
    fix_method = "deterministic"
    if diff is None:
        diff = await patch_generator.generate(message, location, kind="timeout")
        fix_method = "llm"
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method=fix_method)


async def trigger_hallucination(signal) -> Optional[Incident]:
    """
    Entry point for a hallucinated tool call detected on the live trace stream:
    the model invoked a tool outside the registered set. No traceback — the
    detector knows the dispatch site. The correct fix is a real tool-resolution
    step (often a small helper), not a one-line guard, so it goes to the LLM and
    the router will tag it structural. signal is a hallucination.HallucinationSignal.
    Never raises.
    """
    fp = _fingerprint(f"hallucination:{signal.source}:{signal.tool_name}")
    known = ", ".join(signal.available_tools) if signal.available_tools else "the registered tools"
    message = (
        f"Hallucinated tool: the model invoked '{signal.tool_name}', which is not in "
        f"the agent's registered set ({known}). It was dispatched unchecked and did "
        f"no real work — no error, just an empty result."
    )

    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing

        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=ErrorType.HALLUCINATED_TOOL,
            error_message=message,
            interpretation=fallback(ErrorType.HALLUCINATED_TOOL),
            source=signal.source,
            hit_count=1,
            cost_recovered_usd=round(signal.cost_usd, 2) if signal.cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(signal.code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(signal.source, file_path, line)
    if resolved is not None:
        location = resolved.location
    else:
        location = file_reader.read_at(file_path, line, project_root=config.PROJECT_ROOT)
    if location is None:
        print(
            f"\033[33m[orqis] hallucinated tool located at {signal.code_location} but "
            f"source unreadable (GitHub repo + project_root={config.PROJECT_ROOT})\033[0m",
            file=sys.stderr,
        )
        return incident

    incident = await store.update_incident(
        incident.id, **_located_fields(location, resolved)
    )
    await _broadcast("incident.located", incident)

    # No safe one-line template: the fix adds a real tool-resolution step, which
    # the LLM writes through the resilient chain. The router tags it structural.
    diff = await patch_generator.generate(message, location, kind="hallucination")
    if diff is None:
        return incident

    return await _finalize_patch(incident, diff, location, fix_method="llm")


async def trigger_wrong_tool(signal) -> Optional[Incident]:
    """A destructive/write tool run for a read-only request. The guardrail fix is
    agent-specific, so the LLM writes it; the router tags it structural."""
    fp = _fingerprint(f"wrong_tool:{signal.source}:{signal.tool_name}")
    message = (
        f"Wrong tool: the agent ran '{signal.tool_name}' — a destructive/write tool — "
        f"for a read-only request (\"{signal.request}\"). No error, but the wrong and "
        f"potentially harmful action was taken."
    )
    return await _run_llm_trigger(
        fp, ErrorType.WRONG_TOOL, message, signal.source, signal.code_location,
        signal.cost_usd, kind="injection",
    )


async def trigger_cascade(signal) -> Optional[Incident]:
    """A degenerate output poisoned a multi-agent pipeline. Fix: validate outputs
    at the boundary before consuming them (LLM writes it; router tags structural)."""
    fp = _fingerprint(f"cascade:{signal.run_id}")
    stages = " -> ".join(signal.stages) if signal.stages else "the pipeline"
    message = (
        f"Cascade failure: a degenerate output propagated across {stages} in one "
        f"pipeline run — a bad result poisoned the chain instead of being caught at "
        f"a boundary. No error raised; the final output is quietly empty."
    )
    return await _run_llm_trigger(
        fp, ErrorType.CASCADE_FAILURE, message,
        signal.stages[0] if signal.stages else "", signal.code_location,
        signal.cost_usd, kind="corruption",
    )


async def trigger_generic(signal) -> Optional[Incident]:
    """A novel anomaly no named detector claimed — surfaced for investigation, with
    a best-effort LLM fix if we can locate the code."""
    fp = _fingerprint(f"anomaly:{signal.source}")
    message = (
        f"Anomaly: this run cost ${signal.cost_usd:.2f} across {signal.calls} calls — "
        f"{signal.factor:.1f}x the source's ${signal.baseline_usd:.2f} baseline — with no "
        f"specific detector able to name it. Something is wrong; surfacing for review."
    )
    return await _run_llm_trigger(
        fp, ErrorType.ANOMALY, message, signal.source, signal.code_location,
        signal.cost_usd, kind="error",
    )


async def _run_llm_trigger(fp, error_type, message, source, code_location, cost_usd, kind):
    """
    Shared body for the LLM-fixed behavioural triggers: dedup, create + broadcast
    the incident, locate the code, and generate an LLM fix (router tags it
    structural). Surfaces the incident even when no code/fix is available.
    """
    async with _dedup_lock:
        existing = await _dedup_bump(fp)
        if existing is not None:
            return existing
        incident = Incident(
            created_at=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            source_event_id="anomaly",
            error_type=error_type,
            error_message=message,
            interpretation=fallback(error_type),
            source=source,
            hit_count=1,
            cost_recovered_usd=round(cost_usd, 2) if cost_usd else None,
        )
        await store.save_incident(incident)
        await store.dedup_set(fp, incident.id, DEDUP_WINDOW_SECONDS)

    await _broadcast("incident.created", incident)

    file_path, line = _parse_code_location(code_location)
    if file_path is None:
        return incident

    resolved = await source_resolver.resolve_file(source, file_path, line)
    location = resolved.location if resolved is not None else file_reader.read_at(
        file_path, line, project_root=config.PROJECT_ROOT
    )
    if location is None:
        return incident

    incident = await store.update_incident(incident.id, **_located_fields(location, resolved))
    await _broadcast("incident.located", incident)

    diff = await patch_generator.generate(message, location, kind=kind)
    if diff is None:
        return incident
    return await _finalize_patch(incident, diff, location, fix_method="llm")


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
