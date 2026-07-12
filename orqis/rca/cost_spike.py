"""
Token / cost spike detector for agent trace streams.

The runaway-loop detector catches too many calls; this catches calls that each
grow too big. The classic cause is unbounded memory: the agent appends every
turn to its context and never trims it, so per-call input tokens — and the bill —
climb steadily. Nothing errors; the cost just inflates until someone notices.

Detection is baseline-relative, per source. We learn the agent's normal per-call
input-token size from its first few calls, then flag when input tokens stay a
multiple of that baseline for several consecutive calls. Using the agent's own
baseline (not a fixed token number) means a naturally large-context agent never
trips — only a genuine climb away from its own norm does.
"""

import asyncio
from dataclasses import dataclass, field
from statistics import median
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Calls used to establish the agent's normal per-call token size.
BASELINE_CALLS = 4

# How far above baseline counts as a spike, and how many consecutive spiking
# calls before we flag — so a single large call never trips, only a real climb.
SPIKE_FACTOR = 3.0
SUSTAIN = 3

# We measure the size of model calls (that is where tokens/cost accrue).
_COST_KINDS = (EventKind.LLM_START, EventKind.LLM_END)


@dataclass
class _SourceState:
    samples: list = field(default_factory=list)   # first-N input-token sizes
    baseline: Optional[float] = None              # median of the samples
    consecutive_over: int = 0                      # spiking calls in a row
    peak_tokens: int = 0
    spike_cost: float = 0.0
    code_location: Optional[str] = None


@dataclass
class CostSpikeSignal:
    """A confirmed token/cost spike, ready to become an incident."""
    source: str
    baseline_tokens: int
    peak_tokens: int
    factor: float
    cost_usd: float
    code_location: Optional[str]


_states: dict[str, _SourceState] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[CostSpikeSignal]:
    """
    Feed one trace event into the detector. Returns a CostSpikeSignal the first
    time a source's per-call tokens stay SPIKE_FACTOR over its own baseline for
    SUSTAIN consecutive calls, else None. Never raises.
    """
    if event.kind not in _COST_KINDS or not event.input_tokens:
        return None

    tokens = event.input_tokens
    async with _lock:
        st = _states.get(event.source)
        if st is None:
            st = _SourceState()
            _states[event.source] = st
        if event.code_location:
            st.code_location = event.code_location

        # Still learning the baseline.
        if st.baseline is None:
            st.samples.append(tokens)
            if len(st.samples) >= BASELINE_CALLS:
                st.baseline = float(median(st.samples))
            return None

        threshold = st.baseline * SPIKE_FACTOR
        if tokens > threshold:
            st.consecutive_over += 1
            st.peak_tokens = max(st.peak_tokens, tokens)
            if event.cost_usd:
                st.spike_cost += event.cost_usd
        else:
            st.consecutive_over = 0

        if st.consecutive_over >= SUSTAIN and event.source not in _fired:
            _fired.add(event.source)
            _flagged_sources.add(event.source)
            return CostSpikeSignal(
                source=event.source,
                baseline_tokens=int(st.baseline),
                peak_tokens=st.peak_tokens,
                factor=round(st.peak_tokens / st.baseline, 1) if st.baseline else 0.0,
                cost_usd=round(st.spike_cost, 4),
                code_location=st.code_location,
            )
        return None


def is_flagged(source: str) -> bool:
    """True once a cost spike has been confirmed for this source."""
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
