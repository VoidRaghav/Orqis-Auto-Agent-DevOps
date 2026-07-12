"""Shared helpers for Orqis dogfood harness tests."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

SOURCE = "refund-agent"
COST_PER_CALL = 0.0123
DEFAULT_TRACE_COUNT = 10


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_project_root() -> Path:
    return Path(os.getenv("ORQIS_PROJECT_ROOT", str(repo_root() / "test-agent"))).resolve()


def backend_url() -> str:
    return os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000").rstrip("/")


def admin_token() -> str:
    return os.getenv("ORQIS_ADMIN_TOKEN", "").strip()


def admin_headers(trace_id: str | None = None) -> dict[str, str]:
    headers = {"X-Orqis-Admin-Token": admin_token()}
    if trace_id:
        headers["X-Orqis-Trace-Id"] = trace_id
    return headers


def trace_headers(trace_id: str) -> dict[str, str]:
    return {"X-Orqis-Trace-Id": trace_id}


def function_line(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno
    raise ValueError(f"{name} not found in {path}")


def code_location(project_root: Path) -> str:
    refund_file = project_root / "src" / "refund_agent.py"
    line = function_line(refund_file, "resolve_refund")
    return f"{refund_file}:{line}:resolve_refund"


def reset_test_agent(project_root: Path) -> None:
    fixtures_dir = project_root / "fixtures"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    for buggy in fixtures_dir.glob("*.buggy.py"):
        target = src_dir / buggy.name.replace(".buggy.py", ".py")
        target.write_text(buggy.read_text(encoding="utf-8"), encoding="utf-8")


def reset_orqis(client: httpx.Client, trace_id: str) -> None:
    resp = client.post(
        "/demo/reset",
        params={"clear": "true"},
        headers=trace_headers(trace_id),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    assert data.get("ok") is True
    # Local approve path: drop GitHub source mapping left in Redis from demos.
    settings_resp = client.put(
        "/settings",
        json={
            "source_repo_map": {},
            "installation_id": None,
            "repos": [],
            "default_repo": None,
        },
        headers=admin_headers(trace_id),
        timeout=30.0,
    )
    settings_resp.raise_for_status()


def emit_tool_start(
    client: httpx.Client,
    *,
    n: int,
    run_id: str,
    project_root: Path,
    trace_id: str,
) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "tool.start",
        "provider": "langchain",
        "run_id": run_id,
        "model": "gpt-4o",
        "tool_name": "check_order_status",
        "tool_args": '{"order_id": "1042"}',
        "code_location": code_location(project_root),
        "cost_usd": COST_PER_CALL,
        "source": SOURCE,
    }
    resp = client.post(
        "/trace",
        json=event,
        headers=trace_headers(trace_id),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def trigger_runaway_traces(
    client: httpx.Client,
    project_root: Path,
    trace_id: str,
    *,
    count: int = DEFAULT_TRACE_COUNT,
) -> str:
    run_id = str(uuid.uuid4())
    for i in range(1, count + 1):
        emit_tool_start(
            client,
            n=i,
            run_id=run_id,
            project_root=project_root,
            trace_id=trace_id,
        )
        time.sleep(0.2)
    return run_id


def wait_for_patched_incident(
    client: httpx.Client,
    *,
    timeout_s: float = 120.0,
    poll_s: float = 0.5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client.get("/incidents", params={"limit": 50}, timeout=15.0)
        resp.raise_for_status()
        incidents = resp.json()
        if incidents:
            latest = incidents[-1]
            if latest.get("status") == "patched" and latest.get("diff"):
                return latest
        time.sleep(poll_s)
    raise TimeoutError("timed out waiting for patched incident with diff")


def approve_incident(
    client: httpx.Client,
    incident_id: str,
    trace_id: str,
) -> None:
    resp = client.post(
        f"/incidents/{incident_id}/approve",
        headers=admin_headers(trace_id),
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    assert data.get("ok") is True


def behavioral_check_refund(
    project_root: Path,
    *,
    order_id: str = "1042",
    timeout_s: float = 2.0,
) -> str:
    src_dir = project_root / "src"
    refund_file = src_dir / "refund_agent.py"
    ast.parse(refund_file.read_text(encoding="utf-8"))

    snippet = f"""
import sys
sys.path.insert(0, {str(src_dir)!r})
from refund_agent import resolve_refund
print(resolve_refund({order_id!r}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=str(src_dir),
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"resolve_refund failed (rc={proc.returncode}): "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
    return proc.stdout.strip()
