"""
Structured-output / tool-binding drop detector for agent trace streams.

The other detectors watch tools that misbehave. This one watches for a tool that
was supposed to run and silently never did. The canonical cause is the
documented LangChain bug: chaining `.bind_tools(...)` with
`.with_structured_output(...)` drops the tool from the payload, so the model
fills in the structured object itself instead of invoking the tool. The chain
returns clean JSON, so nothing looks wrong — but the tool's real work (routing,
booking, charging) never happened.

The signal is an absence, so we confirm it two ways before flagging: the call
must have bound a tool AND returned structured output AND not invoked any tool —
and it must recur. One such call could be the model legitimately deciding no
tool was needed; the same binding dropped on every varied input is the bug.

This generalises to the tool-invocation-integrity family: any bound/expected
tool that a final answer skips (hallucinated tool, wrong-tool-selection).
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from ..backend.models import TraceEvent

# Dropped-tool calls before we call it systemic (vs. one legitimate no-tool
# answer). The bug drops the binding on every call, so this trips quickly.
THRESHOLD_DROPS = 3


@dataclass
class _SourceState:
    drops: int = 0
    bound_tools: tuple = ()
    cost_usd: float = 0.0
    code_location: Optional[str] = None


@dataclass
class BindingDropSignal:
    """A confirmed tool-binding drop, ready to become an incident."""
    source: str
    bound_tools: list
    drop_count: int
    cost_usd: float
    code_location: Optional[str]


_states: dict[str, _SourceState] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


def _is_drop(event: TraceEvent) -> bool:
    """A call that bound a tool and returned structured output but invoked no
    tool — the binding was dropped."""
    return bool(
        event.bound_tools
        and event.structured_output
        and event.tool_invoked is False
    )


async def observe(event: TraceEvent) -> Optional[BindingDropSignal]:
    """
    Feed one trace event into the detector. Returns a BindingDropSignal the first
    time a source accumulates THRESHOLD_DROPS calls that bound a tool but never
    invoked it while returning structured output, else None. Never raises.
    """
    if not _is_drop(event):
        return None

    async with _lock:
        st = _states.get(event.source)
        if st is None:
            st = _SourceState()
            _states[event.source] = st
        st.drops += 1
        st.bound_tools = tuple(event.bound_tools)
        if event.cost_usd:
            st.cost_usd += event.cost_usd
        if event.code_location:
            st.code_location = event.code_location

        if st.drops >= THRESHOLD_DROPS and event.source not in _fired:
            _fired.add(event.source)
            _flagged_sources.add(event.source)
            return BindingDropSignal(
                source=event.source,
                bound_tools=list(st.bound_tools),
                drop_count=st.drops,
                cost_usd=round(st.cost_usd, 4),
                code_location=st.code_location,
            )
        return None


def is_flagged(source: str) -> bool:
    """True once a tool-binding drop has been confirmed for this source."""
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    """Clear detector state (all sources, or just one so a fixed agent re-runs clean)."""
    if source is None:
        _states.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _states.pop(source, None)
    _fired.discard(source)
    _flagged_sources.discard(source)
