"""
Wrong-tool-selection detector for agent trace streams.

An agent can pick the wrong tool for the job with no error at all: asked to
*check* an email it *sends* one, asked to *view* an invoice it *deletes* it. The
most dangerous version is a read-only request answered with a destructive/write
action, so that is what this catches: the request reads as a lookup, but the
tool the agent ran mutates or sends something.

It is deliberately scoped to that harmful direction (read intent -> destructive
tool) so it stays precise, and it defers to the injection detector — if the
input carried an injection, that is the incident, not a plain wrong-tool pick.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional

from ..backend.models import EventKind, TraceEvent
from . import injection

_TOOL_KINDS = (EventKind.TOOL_START, EventKind.TOOL_END)

# Verbs that mean the tool changes or sends something, not just reads.
_DESTRUCTIVE = (
    "delete", "remove", "drop", "purge", "wipe", "erase", "cancel",
    "send", "email", "post", "publish", "transfer", "pay", "charge", "refund",
    "create", "update", "write", "overwrite", "reset", "revoke", "deactivate",
)

# The request reads as a lookup / question, not a command to change anything.
_READ_INTENT = re.compile(
    r"\b(check|show|view|list|read|find|search|look\s*up|get|display|"
    r"what|which|when|where|how\s+many|status\s+of|tell\s+me)\b",
    re.I,
)
# ... unless it also clearly asks to change something.
_WRITE_INTENT = re.compile(
    r"\b(delete|remove|send|cancel|transfer|pay|charge|refund|create|update|"
    r"change|set|reset|revoke)\b",
    re.I,
)


def _is_destructive(tool: str) -> bool:
    t = tool.lower()
    return any(v in t for v in _DESTRUCTIVE)


def _is_read_intent(text: Optional[str]) -> bool:
    return bool(text) and bool(_READ_INTENT.search(text)) and not _WRITE_INTENT.search(text)


@dataclass
class WrongToolSignal:
    """A confirmed wrong (destructive-on-read) tool pick, ready to become an incident."""
    source: str
    tool_name: str
    request: str
    cost_usd: float
    code_location: Optional[str]


_fired: set[str] = set()
_flagged_sources: set[str] = set()
_lock = asyncio.Lock()


async def observe(event: TraceEvent) -> Optional[WrongToolSignal]:
    """
    Feed one trace event into the detector. Returns a WrongToolSignal the first
    time the agent runs a destructive tool for a read-only request, else None.
    Defers to the injection detector when the input is an injection. Never raises.
    """
    if event.kind not in _TOOL_KINDS or not event.tool_name:
        return None
    if not _is_destructive(event.tool_name):
        return None
    if not _is_read_intent(event.input_text):
        return None
    if injection.is_injection(event.input_text):
        return None  # an injection, not a plain wrong-tool pick

    key = f"{event.source}\x00{event.tool_name}"
    async with _lock:
        if key in _fired:
            return None
        _fired.add(key)
        _flagged_sources.add(event.source)
        return WrongToolSignal(
            source=event.source,
            tool_name=event.tool_name,
            request=(event.input_text or "").strip().replace("\n", " ")[:160],
            cost_usd=round(event.cost_usd or 0.0, 4),
            code_location=event.code_location,
        )


def is_flagged(source: str) -> bool:
    return source in _flagged_sources


def reset(source: Optional[str] = None) -> None:
    if source is None:
        _fired.clear()
        _flagged_sources.clear()
        return
    _flagged_sources.discard(source)
    prefix = f"{source}\x00"
    _fired.difference_update({k for k in _fired if k.startswith(prefix)})
