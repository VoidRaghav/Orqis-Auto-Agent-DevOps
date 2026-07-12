"""Pytest fixtures for Orqis dogfood harness."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
import pytest

from tests.helpers import (
    admin_token,
    backend_url,
    default_project_root,
    reset_orqis,
    reset_test_agent,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _backend_reachable() -> tuple[bool, str]:
    base = backend_url()
    try:
        resp = httpx.get(f"{base}/health", timeout=10.0)
        if resp.status_code != 200:
            return False, f"GET /health returned {resp.status_code}"
        if resp.json().get("status") != "ok":
            return False, f"backend status={resp.json().get('status')!r}"
        probe = httpx.get(f"{base}/incidents?limit=1", timeout=10.0)
        if probe.status_code != 200:
            return (
                False,
                f"GET /incidents returned {probe.status_code} — "
                "is Orqis running on ORQIS_BACKEND_URL?",
            )
        return True, ""
    except Exception as exc:
        return False, str(exc)


@pytest.fixture(scope="session")
def orqis_backend_url() -> str:
    return backend_url()


@pytest.fixture(scope="session")
def orqis_admin_token() -> str:
    return admin_token()


@pytest.fixture(scope="session")
def orqis_project_root() -> Path:
    return default_project_root()


@pytest.fixture(scope="session")
def dogfood_ready(orqis_admin_token: str, orqis_backend_url: str) -> None:
    if not orqis_admin_token:
        pytest.skip("ORQIS_ADMIN_TOKEN is not set (required for dogfood)")
    ok, reason = _backend_reachable()
    if not ok:
        pytest.skip(f"Orqis backend not reachable at {orqis_backend_url}: {reason}")
    refund_agent = default_project_root() / "src" / "refund_agent.py"
    if not refund_agent.is_file():
        pytest.skip(
            f"missing {refund_agent} — set ORQIS_PROJECT_ROOT to test-agent clone"
        )


@pytest.fixture
def trace_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def orqis_client(orqis_backend_url: str) -> httpx.Client:
    with httpx.Client(base_url=orqis_backend_url) as client:
        yield client


@pytest.fixture
def reset_fixtures(
    dogfood_ready: None,
    orqis_client: httpx.Client,
    orqis_project_root: Path,
    trace_id: str,
) -> None:
    reset_orqis(orqis_client, trace_id)
    reset_test_agent(orqis_project_root)
