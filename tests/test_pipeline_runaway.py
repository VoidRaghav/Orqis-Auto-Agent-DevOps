"""Tier A — Orqis pipeline integration (no LLM agent, no Cursor SDK)."""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import (
    approve_incident,
    behavioral_check_refund,
    trigger_runaway_traces,
    wait_for_patched_incident,
)


@pytest.mark.tier_a
def test_pipeline_runaway(
    dogfood_ready: None,
    reset_fixtures: None,
    orqis_client: httpx.Client,
    orqis_project_root,
    trace_id: str,
) -> None:
    trigger_runaway_traces(orqis_client, orqis_project_root, trace_id)

    incident = wait_for_patched_incident(orqis_client)
    incident_id = incident["id"]

    approve_incident(orqis_client, incident_id, trace_id)

    behavioral_check_refund(orqis_project_root)

    resp = orqis_client.get(f"/incidents/{incident_id}", timeout=15.0)
    resp.raise_for_status()
    assert resp.json().get("status") == "approved"
