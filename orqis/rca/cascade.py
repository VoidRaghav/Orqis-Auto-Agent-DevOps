"""
Cascade-failure detector for multi-agent pipelines.

In a pipeline (extract -> summarize -> format, or a chain of agents) one stage
can produce a degenerate output — empty, null, malformed — and the next stage
consumes it, produces its own degenerate output, and passes it on. Each agent
looks fine in isolation; only the whole pipeline fails, quietly, with a clean
but empty final result.

The corruption detector catches one tool feeding one agent bad data. This
catches the *propagation*: within one pipeline run, when two or more distinct
stages produce a degenerate output, a bad result has poisoned the chain rather
than being caught at a boundary.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Distinct stages producing degenerate output in one pipeline before we call it
# a cascade. 2 means the poison crossed at least one boundary uncaught.
THRESHOLD_STAGES = 2

_STAGE_KINDS = (EventKind.TOOL_END, EventKind.CHAIN_END, EventKind.TOOL_START)


def _is_degenerate(result: str) -> bool:
    try:
        value = json.loads(result)
    except Exception:
        return True  # unparseable output is itself poison
    if value is None:
        return True
    if isinstance(value, (dict, list, str)) and len(value) == 0:
        return True
    return False


@dataclass
class _Pipeline:
    bad_stages: set = field(default_factory=set)   # distinct sources with degenerate output
    cost_usd: float = 0.0
    code_location: Optional[str] = None


@dataclass
class CascadeSignal:
    """A confirmed cascade across a pipeline, ready to become an incident."""
    run_id: str
    stages: list
    cost_usd: float
    code_location: Optional[str]


_pipelines: dict[str, _Pipeline] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[CascadeSignal]:
    """
    Feed one trace event into the detector. Returns a CascadeSignal the first
    time two or more distinct stages in one pipeline (run_id) produce a
    degenerate output, else None. Never raises.
    """
    if event.kind not in _STAGE_KINDS or event.tool_result is None or not event.run_id:
        return None
    if not _is_degenerate(event.tool_result):
        return None

    async with _lock:
        p = _pipelines.setdefault(event.run_id, _Pipeline())
        p.bad_stages.add(event.source)
        if event.cost_usd:
            p.cost_usd += event.cost_usd
        if event.code_location:
            p.code_location = event.code_location

        if len(p.bad_stages) >= THRESHOLD_STAGES and event.run_id not in _fired:
            _fired.add(event.run_id)
            _flagged_sources.add(event.source)
            return CascadeSignal(
                run_id=event.run_id,
                stages=sorted(p.bad_stages),
                cost_usd=round(p.cost_usd, 4),
                code_location=p.code_location,
            )
        return None


def is_flagged(source: str) -> bool:
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    if source is None:
        _pipelines.clear()
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    for rid in [r for r, p in _pipelines.items() if source in p.bad_stages]:
        _pipelines.pop(rid, None)
        _fired.discard(rid)
