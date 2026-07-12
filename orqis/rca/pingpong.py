"""
Multi-agent hand-off ping-pong detector for agent trace streams.

The runaway-loop detector watches one agent calling one tool. This watches two
agents bouncing a task between them — A hands to B, B hands back to A, forever,
with no resolver or turn limit. To the loop detector each agent just looks busy;
the pathology only shows in the *alternation*, so that is what we key on.

Per conversation (run_id) we track the hand-off edges. A -> B followed by B -> A
is a reversal; a run of consecutive reversals between the same two agents, with
no third party breaking the cycle, is a ping-pong. We flag once the reversals
pass a threshold — earlier than the loop detector would trip — and trip the
breaker on both agents so the orchestrator stops before it also reads as a
single-agent loop.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Consecutive A<->B reversals before we call it a ping-pong. Fires before the
# loop detector's 8 same-key calls (which would take twice as many hand-offs).
THRESHOLD_REVERSALS = 5

# Reversals older than this belong to a new episode, not the same ping-pong.
WINDOW_SECONDS = 30.0

_HANDOFF_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END)


@dataclass
class _Convo:
    last_edge: Optional[tuple] = None   # (from_agent, to_agent) of the last hand-off
    reversals: int = 0                  # consecutive A<->B reversals
    last_ts: float = 0.0
    agents: set = field(default_factory=set)
    cost_usd: float = 0.0
    code_location: Optional[str] = None


@dataclass
class PingPongSignal:
    """A confirmed multi-agent ping-pong, ready to become an incident."""
    run_id: str
    agents: list           # the two agents bouncing the task
    handoff_count: int     # reversals observed
    sources: list          # trace sources to trip the breaker on
    cost_usd: float
    code_location: Optional[str]


_convos: dict[str, _Convo] = {}
_fired: set[str] = set()          # run_ids already escalated
_tripped_sources: set[str] = set()
_lock = asyncio.Lock()


def _edge(event: TraceEvent) -> Optional[tuple]:
    """Return the (from_agent, to_agent) hand-off edge for this event, or None."""
    frm = getattr(event, "handoff_from", None)
    to = getattr(event, "handoff_to", None)
    if frm and to:
        return (frm, to)
    # Fall back to source + tool_args when explicit hand-off fields are absent.
    if event.tool_name == "handoff" and event.tool_args:
        return (event.source, event.tool_args)
    return None


async def observe(event: TraceEvent) -> Optional[PingPongSignal]:
    """
    Feed one trace event into the detector. Returns a PingPongSignal the first
    time a conversation shows THRESHOLD_REVERSALS consecutive A<->B reversals,
    else None. Never raises.
    """
    if event.kind not in _HANDOFF_KINDS:
        return None
    edge = _edge(event)
    if edge is None:
        return None

    run_id = event.run_id or "default"
    now = time.monotonic()

    async with _lock:
        c = _convos.get(run_id)
        if c is None or now - c.last_ts > WINDOW_SECONDS:
            c = _Convo()
            _convos[run_id] = c

        # A reversal is the previous edge flipped: (a,b) then (b,a).
        if c.last_edge is not None and edge == (c.last_edge[1], c.last_edge[0]):
            c.reversals += 1
        else:
            c.reversals = 1 if c.last_edge is not None else 0
        c.last_edge = edge
        c.last_ts = now
        c.agents.update(edge)
        if event.cost_usd:
            c.cost_usd += event.cost_usd
        if event.code_location:
            c.code_location = event.code_location

        # Only a true two-agent bounce: a third party breaking in resets above.
        if (
            c.reversals >= THRESHOLD_REVERSALS
            and len(c.agents) == 2
            and run_id not in _fired
        ):
            _fired.add(run_id)
            agents = sorted(c.agents)
            # Trip both the bare agent names and any "prefix/agent" trace sources.
            sources = set(agents)
            sources.add(event.source)
            _tripped_sources.update(sources)
            return PingPongSignal(
                run_id=run_id,
                agents=agents,
                handoff_count=c.reversals + 1,
                sources=sorted(sources),
                cost_usd=round(c.cost_usd, 4),
                code_location=c.code_location,
            )
        return None


def is_tripped(source: str) -> bool:
    """True once a ping-pong has been confirmed involving this source."""
    return source in _tripped_sources


def reset(source: Optional[str] = None) -> None:
    """Clear detector state (all, or just conversations/sources for one prefix)."""
    if source is None:
        _convos.clear()
        _fired.clear()
        _tripped_sources.clear()
        return
    _tripped_sources.discard(source)
    for rid in [r for r, c in _convos.items() if source in c.agents]:
        _convos.pop(rid, None)
        _fired.discard(rid)
