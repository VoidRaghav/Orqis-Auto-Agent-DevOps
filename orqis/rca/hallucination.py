"""
Hallucinated-tool detector for agent trace streams.

Sometimes the model doesn't misuse a real tool — it invents one. It emits a tool
call for a name that was never registered ("get_weather_forecast_v2"). Depending
on the framework that raises ToolNotFound or, just as often, fails silently and
the agent answers from nothing. Either way the tool's work never happened.

The signal is exact, not heuristic: the call names a tool outside the set the
agent actually has (carried on the event as bound_tools / the registry). No
baseline to learn and no ambiguity — a tool that isn't registered cannot be
real, so a single such call is already the incident.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from ..backend.models import EventKind, TraceEvent

_TOOL_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END, EventKind.TOOL_ERROR)


@dataclass
class HallucinationSignal:
    """A confirmed hallucinated tool call, ready to become an incident."""
    source: str
    tool_name: str
    available_tools: list
    cost_usd: float
    code_location: Optional[str]


_fired: set[str] = set()          # (source, tool) already escalated
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[HallucinationSignal]:
    """
    Feed one trace event into the detector. Returns a HallucinationSignal the
    first time a tool call names a tool outside the agent's registered set, else
    None. Fires on the first occurrence — a nonexistent tool is unambiguous.
    Never raises.
    """
    if event.kind not in _TOOL_KINDS or not event.tool_name or not event.bound_tools:
        return None
    if event.tool_name in event.bound_tools:
        return None  # a real, registered tool

    key = f"{event.source}\x00{event.tool_name}"
    async with _lock:
        if key in _fired:
            return None
        _fired.add(key)
        _flagged_sources.add(event.source)
        return HallucinationSignal(
            source=event.source,
            tool_name=event.tool_name,
            available_tools=list(event.bound_tools),
            cost_usd=round(event.cost_usd or 0.0, 4),
            code_location=event.code_location,
        )


def is_flagged(source: str) -> bool:
    """True once a hallucinated tool call has been confirmed for this source."""
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    """Clear detector state (all sources, or just one so a fixed agent re-runs clean)."""
    if source is None:
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    prefix = f"{source}\x00"
    _fired.difference_update({k for k in _fired if k.startswith(prefix)})
