"""Incident aggregates for dashboard KPIs."""

from __future__ import annotations

from collections import defaultdict

from ..backend import store


async def incident_stats() -> dict:
    incidents = await store.get_recent_incidents(500)
    total_cost = 0.0
    by_status: dict[str, int] = defaultdict(int)
    for inc in incidents:
        by_status[inc.status.value] += 1
        if inc.cost_recovered_usd:
            total_cost += inc.cost_recovered_usd
    return {
        "total_cost_recovered_usd": round(total_cost, 2),
        "count_by_status": dict(by_status),
        "incident_count": len(incidents),
    }
