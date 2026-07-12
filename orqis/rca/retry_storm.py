"""
Silent retry-storm detector for agent trace streams.

The runaway-loop detector catches a call that never succeeds. This catches a
call that *does* succeed — eventually — after being silently retried past a sane
count. The usual cause is a transient failure (timeout, 429, 503) retried with
no backoff: the user gets a correct answer, so nothing surfaces, but each
operation quietly costs several times what it should and hammers a struggling
downstream.

It keys on the whole transient-failure family, not one error, so the same
detector covers the neighbouring production failures: a plain retry storm, a
rate-limit (429) cascade, and a provider-outage (503) retry loop. We count
consecutive transient failures per (source, tool, args) and reset on the first
success; when that count passes MAX_SILENT_RETRIES the retry is no longer sane.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import ErrorType, EventKind, TraceEvent

# Retries beyond this are no longer a healthy transient recovery. 2 allows the
# occasional blip to self-heal; the 3rd silent retry is the signal.
MAX_SILENT_RETRIES = 2

# Consecutive failures older than this are a new burst, not the same retry.
WINDOW_SECONDS = 30.0

# The transient failures a well-behaved agent retries — and the family this
# detector generalises across (retry storm, 429 cascade, 503 outage).
_TRANSIENT = frozenset({
    ErrorType.TIMEOUT,
    ErrorType.CONNECTION,
    ErrorType.HTTP_ERROR,
    ErrorType.RATE_LIMIT,
})

_TOOL_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END, EventKind.TOOL_ERROR)


@dataclass
class _Burst:
    count: int = 0                       # consecutive transient failures
    last_ts: float = 0.0                 # time of the last failure
    cost_usd: float = 0.0                # spend burned by this burst
    error_type: Optional[str] = None
    code_location: Optional[str] = None


@dataclass
class RetryStormSignal:
    """A confirmed silent retry storm, ready to become an incident."""
    source: str
    tool_name: str
    tool_args: str
    retry_count: int
    error_type: str
    cost_usd: float
    code_location: Optional[str]


_bursts: dict[str, _Burst] = {}       # (source,tool,args) -> current burst
_fired: set[str] = set()              # (source,tool) already escalated
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


def _key(source: str, tool: str, args: str) -> str:
    return f"{source}\x00{tool}\x00{args}"


def _is_transient(event: TraceEvent) -> bool:
    return event.is_error and event.error_type in _TRANSIENT


async def observe(event: TraceEvent) -> Optional[RetryStormSignal]:
    """
    Feed one trace event into the detector. Returns a RetryStormSignal the first
    time a (source, tool) is silently retried past MAX_SILENT_RETRIES, else None.
    A success (or a non-transient result) resets the burst. Never raises.
    """
    if event.kind not in _TOOL_KINDS or not event.tool_name:
        return None

    args = event.tool_args or ""
    key = _key(event.source, event.tool_name, args)
    now = time.monotonic()

    async with _lock:
        # A success — or any non-transient outcome — ends the retry burst.
        if not _is_transient(event):
            _bursts.pop(key, None)
            return None

        burst = _bursts.get(key)
        if burst is None or now - burst.last_ts > WINDOW_SECONDS:
            burst = _Burst()
            _bursts[key] = burst
        burst.count += 1
        burst.last_ts = now
        burst.error_type = event.error_type.value if event.error_type else "TRANSIENT"
        if event.cost_usd:
            burst.cost_usd += event.cost_usd
        if event.code_location:
            burst.code_location = event.code_location

        tool_key = f"{event.source}\x00{event.tool_name}"
        if burst.count > MAX_SILENT_RETRIES and tool_key not in _fired:
            _fired.add(tool_key)
            _flagged_sources.add(event.source)
            return RetryStormSignal(
                source=event.source,
                tool_name=event.tool_name,
                tool_args=args,
                retry_count=burst.count,
                error_type=burst.error_type,
                cost_usd=round(burst.cost_usd, 4),
                code_location=burst.code_location,
            )
        return None


def is_flagged(source: str) -> bool:
    """True once a retry storm has been confirmed for this source."""
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    """Clear detector state (all sources, or just one so a fixed agent re-runs clean)."""
    if source is None:
        _bursts.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    prefix = f"{source}\x00"
    for k in [k for k in _bursts if k.startswith(prefix)]:
        del _bursts[k]
    _fired.difference_update({k for k in _fired if k.startswith(prefix)})
