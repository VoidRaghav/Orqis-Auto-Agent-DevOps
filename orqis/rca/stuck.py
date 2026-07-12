"""
Stuck / zero-output agent detector for agent trace streams.

Every other detector reacts to events arriving. This one reacts to events NOT
arriving. An agent can enter a state where it just stops — waiting on a tool call
that never resolves, a poorly bounded state machine — and goes silent. No error,
no crash, no cost, nothing to react to. The only signal is the absence of one.

So this detector is a watchdog, not an observer. observe() records when an
operation starts (a *.start with no matching *.end) and clears it when it
finishes. A background sweep() then finds operations that have been open with no
activity for longer than STUCK_SECONDS and reports them. It is driven by the
server's watchdog loop, not by the trace handler.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# How long an operation may be open with no progress before it is stuck. Kept
# modest so a real stall is caught quickly; raise it for slow, long-running tools.
STUCK_SECONDS = 8.0

_START_KINDS = (EventKind.LLM_START, EventKind.TOOL_START, EventKind.CHAIN_START)
_END_KINDS = (
    EventKind.LLM_END, EventKind.LLM_ERROR,
    EventKind.TOOL_END, EventKind.TOOL_ERROR,
    EventKind.CHAIN_END, EventKind.CHAIN_ERROR,
)


@dataclass
class _Open:
    ts: float                       # server-side monotonic time the op started
    source: str
    kind: str
    tool_name: Optional[str]
    code_location: Optional[str]
    cost_usd: float


@dataclass
class StuckSignal:
    """A confirmed stuck / zero-output agent, ready to become an incident."""
    source: str
    run_id: str
    operation: str
    seconds_stuck: float
    code_location: Optional[str]
    cost_usd: float


_open: dict[str, _Open] = {}     # run_id -> the operation currently open on it
_fired: set[str] = set()         # run_ids already escalated
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> None:
    """
    Track operation start/end so the watchdog can spot one that never finishes.
    A start opens the run; a matching end (or error) closes it. Never raises.
    """
    if not event.run_id:
        return
    async with _lock:
        if event.kind in _START_KINDS:
            _open[event.run_id] = _Open(
                ts=time.monotonic(),
                source=event.source,
                kind=event.kind.value,
                tool_name=event.tool_name,
                code_location=event.code_location,
                cost_usd=event.cost_usd or 0.0,
            )
        elif event.kind in _END_KINDS:
            _open.pop(event.run_id, None)
            _fired.discard(event.run_id)


async def sweep() -> list[StuckSignal]:
    """Return a signal for each operation open with no progress past STUCK_SECONDS,
    firing at most once per run. Called periodically by the server watchdog."""
    now = time.monotonic()
    out: list[StuckSignal] = []
    async with _lock:
        for run_id, op in _open.items():
            if now - op.ts >= STUCK_SECONDS and run_id not in _fired:
                _fired.add(run_id)
                _flagged_sources.add(op.source)
                out.append(StuckSignal(
                    source=op.source,
                    run_id=run_id,
                    operation=op.tool_name or op.kind,
                    seconds_stuck=round(now - op.ts, 1),
                    code_location=op.code_location,
                    cost_usd=round(op.cost_usd, 4),
                ))
    return out


def is_flagged(source: str) -> bool:
    """True once a stuck agent has been confirmed for this source."""
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    """Clear watchdog state (all sources, or just one so a fixed agent re-runs clean)."""
    if source is None:
        _open.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    for rid in [r for r, op in _open.items() if op.source == source]:
        _open.pop(rid, None)
        _fired.discard(rid)
