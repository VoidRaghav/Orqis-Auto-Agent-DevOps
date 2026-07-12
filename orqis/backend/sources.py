"""Recent log/trace sources for Settings autocomplete."""

from __future__ import annotations

from ..backend import store


async def recent_sources(limit: int = 50) -> list[str]:
    seen: set[str] = set()
    for inc in await store.get_recent_incidents(limit):
        src = (inc.source or "").strip()
        if src and src != "unknown":
            seen.add(src)
    for ev in await store.get_recent_events(limit):
        src = (ev.source or "").strip()
        if src and src != "unknown":
            seen.add(src)
    for tr in await store.get_recent_traces(limit):
        src = (tr.source or "").strip()
        if src and src != "unknown":
            seen.add(src)
    return sorted(seen)[:limit]
