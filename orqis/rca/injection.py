"""
Prompt-injection / behaviour-divergence detector for agent trace streams.

An agent settles into a stable repertoire of tools. A prompt injection —
"ignore all previous instructions and ..." — tries to push it outside that
repertoire into something dangerous (email exfiltration, fund transfer, data
deletion). This detector watches for exactly that: a tool call that falls
outside the agent's established set, driven by an input that carries an injection
pattern. Both signals together mean the injection didn't just arrive, it worked.

Requiring both the out-of-set tool AND the injection text keeps it precise — an
agent legitimately gaining a new tool won't trip it, and an injection the agent
correctly refused (no divergent tool) won't either. Because a single successful
injection is already an incident, it fires on the first occurrence, not on
recurrence.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional

from ..backend.models import EventKind, TraceEvent

# Established tool calls before we trust the baseline set — so the first couple
# of normal calls define "allowed" before we judge anything as divergent.
MIN_BASELINE = 2

_TOOL_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END)

# Common prompt-injection phrasings. Deliberately broad but anchored on the
# override intent, so ordinary user text doesn't match.
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|the\s+|any\s+)?(previous|prior|above|earlier|your)\s+"
               r"(instructions|prompts?|messages?|rules|directions)", re.I),
    re.compile(r"disregard\s+(all\s+|the\s+|any\s+)?(previous|prior|above|your)", re.I),
    re.compile(r"forget\s+(everything|all|your\s+(instructions|rules))", re.I),
    re.compile(r"you\s+are\s+now\s+(an?\s+)?(admin|root|developer|dan|unrestricted)", re.I),
    re.compile(r"(reveal|print|show|leak)\s+(your\s+)?(system\s+)?(prompt|instructions)", re.I),
    re.compile(r"override\s+(your\s+)?(safety|guardrails|restrictions)", re.I),
]


def is_injection(text: Optional[str]) -> bool:
    return bool(text) and any(p.search(text) for p in _INJECTION_PATTERNS)


@dataclass
class _SourceState:
    allowed: set = field(default_factory=set)   # the agent's established tool set
    calls: int = 0


@dataclass
class InjectionSignal:
    """A confirmed successful prompt injection, ready to become an incident."""
    source: str
    tool_name: str
    allowed_tools: list
    snippet: str            # the offending input, trimmed
    cost_usd: float
    code_location: Optional[str]


_states: dict[str, _SourceState] = {}
_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[InjectionSignal]:
    """
    Feed one trace event into the detector. Returns an InjectionSignal the first
    time an agent calls a tool outside its established set on an input that
    carries an injection pattern, else None. Never raises.
    """
    if event.kind not in _TOOL_KINDS or not event.tool_name:
        return None

    async with _lock:
        st = _states.get(event.source)
        if st is None:
            st = _SourceState()
            _states[event.source] = st

        injected = is_injection(event.input_text)
        known = event.tool_name in st.allowed

        # A divergent tool driven by an injection, once a baseline exists — the
        # injection succeeded.
        if (
            injected
            and not known
            and st.calls >= MIN_BASELINE
            and event.source not in _fired
        ):
            _fired.add(event.source)
            _flagged_sources.add(event.source)
            snippet = (event.input_text or "").strip().replace("\n", " ")[:160]
            return InjectionSignal(
                source=event.source,
                tool_name=event.tool_name,
                allowed_tools=sorted(st.allowed),
                snippet=snippet,
                cost_usd=round(event.cost_usd or 0.0, 4),
                code_location=event.code_location,
            )

        # Learn the baseline only from clean (non-injection) calls, so an
        # injected tool never gets whitelisted.
        if not injected:
            st.allowed.add(event.tool_name)
            st.calls += 1
        return None


def is_flagged(source: str) -> bool:
    """True once a successful prompt injection has been confirmed for this source."""
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
