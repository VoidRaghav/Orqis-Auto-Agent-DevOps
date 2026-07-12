"""
Generic anomaly catch-all for novel / unknown agent failures.

The other detectors each know one failure shape. This one knows none — it is the
safety net for failures we haven't named yet. It learns each source's normal
cost-per-run and flags a run that blows far past that baseline when no specific
detector has already claimed it. Most real failures — known or brand new — show
up as abnormal resource use, so a big, unexplained cost spike on a run is a
symptom worth surfacing even without a named cause.

It defers to every specific detector (checked via their is_flagged/is_tripped),
so it never double-reports a loop, a cost spike, a retry storm, and so on — it
only fires on the leftover: something is clearly wrong, and nothing else saw it.
"""

import asyncio
from dataclasses import dataclass
from statistics import median
from typing import Optional

from ..backend.models import TraceEvent

# A run must cost this multiple of the source's normal run before it counts as a
# novel anomaly — high, because this is a last-resort net, not a fine gauge.
FACTOR = 5.0

# Completed runs needed before the baseline is trustworthy.
MIN_BASELINE_RUNS = 3


@dataclass
class _Run:
    run_id: str
    cost_usd: float = 0.0
    calls: int = 0
    code_location: Optional[str] = None


@dataclass
class AnomalySignal:
    source: str
    run_id: str
    cost_usd: float
    baseline_usd: float
    factor: float
    calls: int
    code_location: Optional[str]


_baseline: dict[str, list] = {}     # source -> recent finalized run costs
_current: dict[str, _Run] = {}      # source -> the run in progress
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


def _specific_flagged(source: str) -> bool:
    """True if any named detector already owns this source — don't double-report."""
    from . import (
        anomaly, binding_drop, cascade, corruption, cost_spike, hallucination,
        injection, overflow, pingpong, retry_storm, stuck, wrong_tool,
    )
    if anomaly.is_tripped(source) or pingpong.is_tripped(source):
        return True
    for mod in (binding_drop, cascade, corruption, cost_spike, hallucination,
                injection, overflow, retry_storm, stuck, wrong_tool):
        if mod.is_flagged(source):
            return True
    return False


async def observe(event: TraceEvent) -> Optional[AnomalySignal]:
    """
    Feed one trace event into the detector. Returns an AnomalySignal the first
    time a run's cost blows past FACTOR x the source's baseline with no specific
    detector already on it, else None. Never raises.
    """
    if not event.source or not event.run_id or event.cost_usd is None:
        return None

    async with _lock:
        cur = _current.get(event.source)
        if cur is None or cur.run_id != event.run_id:
            # A new run began — finalize the previous run into the baseline.
            if cur is not None:
                _baseline.setdefault(event.source, []).append(cur.cost_usd)
                _baseline[event.source] = _baseline[event.source][-20:]
            cur = _Run(event.run_id)
            _current[event.source] = cur

        cur.cost_usd += event.cost_usd
        cur.calls += 1
        if event.code_location:
            cur.code_location = event.code_location

        base = _baseline.get(event.source, [])
        if len(base) < MIN_BASELINE_RUNS or event.source in _fired:
            return None
        med = median(base)
        if med <= 0 or cur.cost_usd <= FACTOR * med:
            return None
        if _specific_flagged(event.source):
            return None  # a named detector already owns this

        _fired.add(event.source)
        _flagged_sources.add(event.source)
        return AnomalySignal(
            source=event.source,
            run_id=event.run_id,
            cost_usd=round(cur.cost_usd, 4),
            baseline_usd=round(med, 4),
            factor=round(cur.cost_usd / med, 1),
            calls=cur.calls,
            code_location=cur.code_location,
        )


def is_flagged(source: str) -> bool:
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    if source is None:
        _baseline.clear()
        _current.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _baseline.pop(source, None)
    _current.pop(source, None)
    _fired.discard(source)
    _flagged_sources.discard(source)
