"""
Behavioural anomaly detector for agent trace streams.

Tracebacks catch crashes. This catches the failure mode that never raises:
an agent calling the same tool, with the same arguments, over and over,
because it has no exit condition for an ambiguous result. The function works.
The tool works. Nothing throws. Money just drains.

Detection is a sliding window over the live TraceEvent stream — no LLM, no I/O.
When one (source, tool, args) key is invoked more than THRESHOLD times within
WINDOW_SECONDS, we flag a runaway loop and report the accumulated cost. Each
key fires at most once until reset(), so a 200-call loop yields one incident,
not 200.

A flagged source is "tripped": the server reports this back on the next trace
so the agent can break its own loop — the closed-loop circuit breaker.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Identical calls within the window before we call it a loop. Tuned so a genuine
# retry-with-backoff (a handful of attempts) never trips, but a no-exit loop does.
THRESHOLD = 8

# Sliding window. Only calls inside this many seconds count toward the threshold,
# so a tool legitimately called once a minute for an hour never accumulates.
WINDOW_SECONDS = 30.0

# Tool-call event kinds. We key off starts so the loop is caught as it happens,
# not after each call also reports an end.
_LOOP_KINDS = (EventKind.TOOL_START,)


@dataclass
class _Bucket:
    timestamps: deque = field(default_factory=deque)  # call times inside the window
    cost_usd: float = 0.0                              # total burned by this key
    run_ids: set = field(default_factory=set)          # distinct agent runs involved
    tool_name: str = ""
    tool_args: str = ""
    code_location: Optional[str] = None
    source: str = ""


@dataclass
class AnomalySignal:
    """A confirmed runaway loop, ready to become an incident."""
    source: str
    tool_name: str
    tool_args: str
    call_count: int
    window_seconds: float
    cost_usd: float
    code_location: Optional[str]  # "file.py:line:function"


# key -> rolling state. key = "source\x00tool\x00args".
_buckets: dict[str, _Bucket] = {}
# keys already escalated — suppresses duplicate incidents for the same loop.
_fired: set[str] = set()
# sources with a live runaway loop — drives the circuit breaker.
_tripped: set[str] = set()
# Serialises the read-modify-write on shared state across concurrent traces.
_lock = asyncio.Lock()


from ..backend.tenancy import get_workspace_id


def _key(source: str, tool: str, args: str) -> str:
    wid = get_workspace_id()
    return f"{wid}\x00{source}\x00{tool}\x00{args}"


async def observe(event: TraceEvent) -> Optional[AnomalySignal]:
    """
    Feed one trace event into the detector.

    Returns an AnomalySignal the first time a (source, tool, args) key crosses
    the loop threshold, otherwise None. Never raises — a detector fault must
    never take down trace ingestion.
    """
    if event.kind not in _LOOP_KINDS or not event.tool_name:
        return None

    args = event.tool_args or ""
    key = _key(event.source, event.tool_name, args)
    now = time.monotonic()

    async with _lock:
        bucket = _buckets.get(key)
        if bucket is None:
            bucket = _Bucket(
                tool_name=event.tool_name,
                tool_args=args,
                code_location=event.code_location,
                source=event.source,
            )
            _buckets[key] = bucket

        # Newest call wins for location — the loop body is what we want to patch.
        if event.code_location:
            bucket.code_location = event.code_location
        if event.cost_usd:
            bucket.cost_usd += event.cost_usd
        if event.run_id:
            bucket.run_ids.add(event.run_id)

        bucket.timestamps.append(now)
        cutoff = now - WINDOW_SECONDS
        while bucket.timestamps and bucket.timestamps[0] < cutoff:
            bucket.timestamps.popleft()

        if len(bucket.timestamps) < THRESHOLD or key in _fired:
            return None

        # Crossed the threshold for the first time — escalate exactly once.
        _fired.add(key)
        _tripped.add(f"{get_workspace_id()}\x00{event.source}")
        return AnomalySignal(
            source=event.source,
            tool_name=bucket.tool_name,
            tool_args=bucket.tool_args,
            call_count=len(bucket.timestamps),
            window_seconds=WINDOW_SECONDS,
            cost_usd=round(bucket.cost_usd, 2),
            code_location=bucket.code_location,
        )


def is_tripped(source: str) -> bool:
    """True once a runaway loop has been confirmed for this source."""
    wid = get_workspace_id()
    return f"{wid}\x00{source}" in _tripped


def reset(source: Optional[str] = None) -> None:
    """
    Clear detector state for the current workspace. With a source, clears only
    that source; with none, clears all buckets/fired/tripped keys for this workspace.
    """
    wid = get_workspace_id()
    if source is None:
        ws_prefix = f"{wid}\x00"
        for key in [k for k in list(_buckets) if k.startswith(ws_prefix)]:
            del _buckets[key]
        _fired.difference_update({k for k in _fired if k.startswith(ws_prefix)})
        _tripped.difference_update({k for k in _tripped if k.startswith(ws_prefix)})
        return
    trip_key = f"{wid}\x00{source}"
    _tripped.discard(trip_key)
    prefix = f"{wid}\x00{source}\x00"
    for key in [k for k in _buckets if k.startswith(prefix)]:
        del _buckets[key]
    _fired.difference_update({k for k in _fired if k.startswith(prefix)})
