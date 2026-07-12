"""
Context-window overflow detector for agent trace streams.

The cost-spike detector catches a context that *grows* past the agent's own
baseline. This catches a context that sits at or over the *model's hard limit* —
a different failure with a worse consequence: the API silently truncates the
prompt (often dropping the system instructions) and the agent answers off-policy.
A relative detector is blind to it, because a context that is huge from the first
call never climbs; you have to know the model's window to see the danger.

We keep a small map of model -> context window and flag when per-call input
tokens cross OVERFLOW_FRACTION of that window for a few consecutive calls. Only
models whose window we know are checked, so an unknown model never false-fires.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Fraction of the window at which truncation risk is real (the last ~10% is
# where system prompts start getting clipped).
OVERFLOW_FRACTION = 0.90

# Consecutive over-window calls before flagging — one large call could be a
# genuine one-off; a sustained over-window prompt is a broken context strategy.
THRESHOLD = 3

_COST_KINDS = (EventKind.LLM_START, EventKind.LLM_END)

# Known context windows (tokens). Matched by longest-prefix so "gpt-4o" wins over
# "gpt-4". Unknown models are skipped rather than guessed.
_WINDOWS = {
    "gpt-4o": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5": 16_385,
    "o1": 200_000,
    "o3": 200_000,
    "claude": 200_000,
    "gemini-1.5": 1_000_000,
    "gemini-2": 1_000_000,
    "gemini": 1_000_000,
    "llama-3": 128_000,
    "llama": 8_192,
}


def window_for(model: Optional[str]) -> Optional[int]:
    """Return the context window for a model id, matching the longest known prefix."""
    if not model:
        return None
    m = model.lower()
    best = None
    for prefix, size in _WINDOWS.items():
        if m.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, size)
    return best[1] if best else None


@dataclass
class _SourceState:
    over: int = 0
    peak_tokens: int = 0
    window: int = 0
    model: str = ""
    cost_usd: float = 0.0
    code_location: Optional[str] = None


@dataclass
class OverflowSignal:
    """A confirmed context-window overflow, ready to become an incident."""
    source: str
    model: str
    window: int
    peak_tokens: int
    fraction: float
    cost_usd: float
    code_location: Optional[str]


_states: dict[str, _SourceState] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[OverflowSignal]:
    """
    Feed one trace event into the detector. Returns an OverflowSignal the first
    time a source's input tokens cross OVERFLOW_FRACTION of its model's window for
    THRESHOLD consecutive calls, else None. Never raises.
    """
    if event.kind not in _COST_KINDS or not event.input_tokens:
        return None
    window = window_for(event.model)
    if window is None:
        return None

    async with _lock:
        st = _states.get(event.source)
        if st is None:
            st = _SourceState()
            _states[event.source] = st
        st.window = window
        st.model = event.model or ""
        if event.code_location:
            st.code_location = event.code_location

        if event.input_tokens > OVERFLOW_FRACTION * window:
            st.over += 1
            st.peak_tokens = max(st.peak_tokens, event.input_tokens)
            if event.cost_usd:
                st.cost_usd += event.cost_usd
        else:
            st.over = 0

        if st.over >= THRESHOLD and event.source not in _fired:
            _fired.add(event.source)
            _flagged_sources.add(event.source)
            return OverflowSignal(
                source=event.source,
                model=st.model,
                window=window,
                peak_tokens=st.peak_tokens,
                fraction=round(st.peak_tokens / window, 2),
                cost_usd=round(st.cost_usd, 4),
                code_location=st.code_location,
            )
        return None


def is_flagged(source: str) -> bool:
    """True once a context overflow has been confirmed for this source."""
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
