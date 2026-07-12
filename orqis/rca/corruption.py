"""
Silent tool-call corruption detector for agent trace streams.

The runaway-loop detector catches an agent that never stops. This catches the
opposite and subtler failure: a tool that *works* almost every time suddenly
returns an empty or degenerate payload (a downstream timeout, a partial
response, a changed schema), and the agent — having no validation — consumes it
and keeps going. Nothing throws. No traceback. The corruption just propagates
into every downstream step.

Detection is baseline-relative, so it never fires on a tool that legitimately
returns empty. For each (source, tool) we learn the tool's normal schema from
its healthy calls. Only once that baseline is established do degenerate results
count — and only when they recur (the agent kept consuming them) do we flag it.
No hardcoded "call N"; the signal is the deviation from the tool's own norm.
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Healthy (non-degenerate) results a tool must produce before we trust that it
# is *supposed* to return data — guards against flagging a genuinely-empty tool.
MIN_BASELINE = 2

# Degenerate results inside the window before we call it corruption. >1 so a
# single transient blip never trips; the agent must be repeatedly consuming junk.
THRESHOLD = 3

# Sliding window for counting degenerate results.
WINDOW_SECONDS = 60.0

# We inspect the payload a tool returned. The agent reports it on the tool call.
_RESULT_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END)


@dataclass
class _ToolState:
    healthy_keys: set = field(default_factory=set)   # schema learned from good calls
    healthy_count: int = 0                            # good calls seen
    corrupt_ts: deque = field(default_factory=deque)  # degenerate call times in window
    corrupt_cost: float = 0.0                         # spend on degenerate calls
    code_location: Optional[str] = None
    source: str = ""
    tool_name: str = ""


@dataclass
class CorruptionSignal:
    """A confirmed silent-corruption pattern, ready to become an incident."""
    source: str
    tool_name: str
    corrupt_count: int
    healthy_count: int
    expected_keys: list          # the schema the tool normally returns
    window_seconds: float
    cost_usd: float
    code_location: Optional[str]


_states: dict[str, _ToolState] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


def _key(source: str, tool: str) -> str:
    return f"{source}\x00{tool}"


def _parse(result: str):
    """Parse the tool payload. Returns (value, ok) — ok=False means unparseable
    (itself a form of corruption once a baseline exists)."""
    try:
        return json.loads(result), True
    except Exception:
        return None, False


def _is_degenerate(value, ok: bool, healthy_keys: set) -> bool:
    """A payload is degenerate if it carries no usable data, or if it has lost
    the schema the tool established (all known keys gone)."""
    if not ok:
        return True
    if value is None:
        return True
    if isinstance(value, (dict, list, str)) and len(value) == 0:
        return True
    if isinstance(value, dict) and healthy_keys and healthy_keys.isdisjoint(value.keys()):
        return True
    return False


async def observe(event: TraceEvent) -> Optional[CorruptionSignal]:
    """
    Feed one trace event into the detector. Returns a CorruptionSignal the first
    time a (source, tool) with an established healthy baseline crosses the
    degenerate-result threshold, else None. Never raises.
    """
    if event.kind not in _RESULT_KINDS or not event.tool_name or event.tool_result is None:
        return None

    value, ok = _parse(event.tool_result)
    key = _key(event.source, event.tool_name)
    now = time.monotonic()

    async with _lock:
        st = _states.get(key)
        if st is None:
            st = _ToolState(source=event.source, tool_name=event.tool_name)
            _states[key] = st
        if event.code_location:
            st.code_location = event.code_location

        if _is_degenerate(value, ok, st.healthy_keys):
            st.corrupt_ts.append(now)
            if event.cost_usd:
                st.corrupt_cost += event.cost_usd
            cutoff = now - WINDOW_SECONDS
            while st.corrupt_ts and st.corrupt_ts[0] < cutoff:
                st.corrupt_ts.popleft()

            # Only corruption once we know the tool is *meant* to return data.
            if (
                st.healthy_count >= MIN_BASELINE
                and len(st.corrupt_ts) >= THRESHOLD
                and key not in _fired
            ):
                _fired.add(key)
                _flagged_sources.add(event.source)
                return CorruptionSignal(
                    source=event.source,
                    tool_name=event.tool_name,
                    corrupt_count=len(st.corrupt_ts),
                    healthy_count=st.healthy_count,
                    expected_keys=sorted(st.healthy_keys),
                    window_seconds=WINDOW_SECONDS,
                    cost_usd=round(st.corrupt_cost, 4),
                    code_location=st.code_location,
                )
            return None

        # Healthy result — learn/refresh the tool's normal schema.
        st.healthy_count += 1
        if isinstance(value, dict):
            st.healthy_keys.update(value.keys())
        return None


def is_flagged(source: str) -> bool:
    """True once silent corruption has been confirmed for this source."""
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    """Clear detector state (all sources, or just one so a fixed agent re-runs clean)."""
    if source is None:
        _states.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    prefix = f"{source}\x00"
    for k in [k for k in _states if k.startswith(prefix)]:
        del _states[k]
    _fired.difference_update({k for k in _fired if k.startswith(prefix)})
