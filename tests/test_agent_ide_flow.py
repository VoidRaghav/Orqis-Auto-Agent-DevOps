"""Tier B — Cursor SDK agent uses Orqis MCP before approving."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import pytest

from tests.helpers import (
    backend_url,
    behavioral_check_refund,
    trigger_runaway_traces,
    wait_for_patched_incident,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("CURSOR_API_KEY", "").strip(),
    reason="CURSOR_API_KEY not set (required for Tier B)",
)

PROMPT = (
    "Use Orqis MCP tools to investigate the latest incident. "
    "Call list_incidents and get_incident before taking any fix action. "
    "Apply the fix via approve_incident or implement the same change manually. "
    "Do not guess the fix without reading Orqis first."
)

MCP_PROXY = Path(__file__).resolve().parent / "mcp_call_log.py"


def _load_call_log(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _assert_mcp_ordering(entries: list[dict]) -> None:
    tools = [e.get("tool", "") for e in entries]
    if "approve_incident" not in tools:
        return
    approve_idx = tools.index("approve_incident")
    assert "list_incidents" in tools[:approve_idx], (
        "approve_incident called before list_incidents"
    )
    assert "get_incident" in tools[:approve_idx], (
        "approve_incident called before get_incident"
    )
    approve_ids = [
        e.get("args", {}).get("incident_id")
        for e in entries
        if e.get("tool") == "approve_incident"
    ]
    assert len(approve_ids) == len(set(approve_ids)), (
        "approve_incident called twice on the same incident id"
    )


@pytest.mark.tier_b
def test_agent_ide_flow(
    dogfood_ready: None,
    reset_fixtures: None,
    orqis_client: httpx.Client,
    orqis_project_root: Path,
    orqis_admin_token: str,
    trace_id: str,
) -> None:
    cursor_sdk = pytest.importorskip("cursor_sdk")
    from cursor_sdk import Agent, LocalAgentOptions

    trigger_runaway_traces(orqis_client, orqis_project_root, trace_id)
    wait_for_patched_incident(orqis_client)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as log_file:
        log_path = Path(log_file.name)

    try:
        mcp_env = {
            "ORQIS_BACKEND_URL": backend_url(),
            "ORQIS_ADMIN_TOKEN": orqis_admin_token,
            "ORQIS_MCP_CALL_LOG": str(log_path),
        }
        with Agent.create(
            model="composer-2.5",
            api_key=os.environ["CURSOR_API_KEY"],
            local=LocalAgentOptions(cwd=str(orqis_project_root), setting_sources=[]),
            mcp_servers=[
                {
                    "name": "orqis",
                    "command": sys.executable,
                    "args": [str(MCP_PROXY)],
                    "env": mcp_env,
                }
            ],
        ) as agent:
            run = agent.send(PROMPT)
            result = run.wait()

        print(f"trace_id={trace_id} run_id={run.id}")

        assert result.status == "finished", f"agent run failed: status={result.status}"

        call_log = _load_call_log(log_path)
        _assert_mcp_ordering(call_log)

        behavioral_check_refund(orqis_project_root)

        resp = orqis_client.get("/incidents", params={"limit": 50}, timeout=15.0)
        resp.raise_for_status()
        incidents = resp.json()
        assert incidents, "expected at least one incident after agent run"
        latest = incidents[-1]
        assert latest.get("status") in ("approved", "resolved"), (
            f"expected approved or resolved, got {latest.get('status')!r}"
        )
    finally:
        log_path.unlink(missing_ok=True)
