"""HTTP-layer tenancy tests (require local Redis)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from orqis import config
from orqis.backend.server import app
from tests.tenancy_helpers import (
    clear_workspace_sync,
    create_api_key_sync,
    redis_available,
    seed_incident_sync,
    session_cookies,
)


@pytest.fixture(scope="module")
def redis_ready():
    if not redis_available():
        pytest.skip("Redis not available")


@pytest.fixture
def mt_env(monkeypatch):
    monkeypatch.setattr(config, "MULTI_TENANT", True)
    monkeypatch.setattr(config, "HOSTED", True)
    monkeypatch.setattr(config, "DEV_MODE", False)
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(
        config,
        "SESSION_SECRET",
        "test-session-secret-32-characters-minimum",
    )
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    monkeypatch.setattr(config, "GITHUB_OAUTH_CLIENT_ID", "test-oauth-id")
    monkeypatch.setattr(config, "GITHUB_OAUTH_CLIENT_SECRET", "test-oauth-secret")
    monkeypatch.setattr(config, "GITHUB_APP_ID", "")


@pytest.fixture
def client(mt_env, redis_ready):
    with TestClient(app) as c:
        yield c


def test_unauthenticated_dashboard_reads_401(client):
    assert client.get("/incidents").status_code == 401
    assert client.get("/settings").status_code == 401
    assert client.get("/events").status_code == 401


def test_unauthenticated_ingest_401(client):
    resp = client.post("/ingest", json={"lines": ["error"], "source": "test"})
    assert resp.status_code == 401


def test_cross_tenant_incident_isolation(client):
    ws_a = f"http_a_{uuid.uuid4().hex[:8]}"
    ws_b = f"http_b_{uuid.uuid4().hex[:8]}"
    inc_id = str(uuid.uuid4())
    seed_incident_sync(ws_a, inc_id, "tenant-a-secret")

    resp_a = client.get("/incidents", cookies=session_cookies(ws_a))
    assert resp_a.status_code == 200
    assert inc_id in {i["id"] for i in resp_a.json()}

    resp_b = client.get("/incidents", cookies=session_cookies(ws_b))
    assert resp_b.status_code == 200
    assert inc_id not in {i["id"] for i in resp_b.json()}

    assert (
        client.get(f"/incidents/{inc_id}", cookies=session_cookies(ws_b)).status_code
        == 404
    )

    clear_workspace_sync(ws_a)
    clear_workspace_sync(ws_b)


def test_hosted_blocks_admin_cross_tenant_write(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "test-admin-token-for-mcp-only")
    ws = f"http_admin_{uuid.uuid4().hex[:8]}"
    inc_id = str(uuid.uuid4())
    seed_incident_sync(ws, inc_id, "admin-test")

    resp = client.post(
        f"/incidents/{inc_id}/dismiss",
        headers={
            "X-Orqis-Admin-Token": config.ADMIN_TOKEN,
            "X-Orqis-Workspace": ws,
        },
    )
    assert resp.status_code == 401
    clear_workspace_sync(ws)


def test_auth_me_optional(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["multi_tenant"] is True

    ws = f"http_me_{uuid.uuid4().hex[:8]}"
    resp2 = client.get("/auth/me", cookies=session_cookies(ws, login="alice"))
    assert resp2.status_code == 200
    assert resp2.json()["authenticated"] is True
    assert resp2.json()["login"] == "alice"


def test_ingest_requires_valid_api_key(client):
    ws = f"http_ingest_{uuid.uuid4().hex[:8]}"
    key = create_api_key_sync(ws)

    assert client.post("/ingest", json={"lines": ["error line"], "source": "test"}).status_code == 401

    good = client.post(
        "/ingest",
        json={"lines": ["error line"], "source": "test"},
        headers={"Authorization": f"Bearer {key}"},
    )
    assert good.status_code == 202


def test_hosted_api_key_write_allowed(client):
    ws = f"http_write_{uuid.uuid4().hex[:8]}"
    inc_id = str(uuid.uuid4())
    key = create_api_key_sync(ws)
    seed_incident_sync(ws, inc_id, "api-key-write")

    resp = client.post(
        f"/incidents/{inc_id}/dismiss",
        headers={"Authorization": f"Bearer {key}"},
    )
    assert resp.status_code == 200
    clear_workspace_sync(ws)


def test_ws_ticket_single_use(client):
    from starlette.websockets import WebSocketDisconnect

    ws = f"http_ws_{uuid.uuid4().hex[:8]}"
    cookies = session_cookies(ws)

    ticket = client.get("/auth/ws-ticket", cookies=cookies).json()["ticket"]

    with client.websocket_connect(f"/ws?ticket={ticket}"):
        pass

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws?ticket={ticket}"):
            pass


def test_pr_webhook_unbound_install_is_pending():
    import asyncio

    from orqis.integrations.github import webhooks

    payload = {
        "action": "closed",
        "pull_request": {"merged": True, "number": 1, "merge_commit_sha": "abc"},
        "repository": {"full_name": "org/repo"},
    }
    result = asyncio.run(webhooks._handle_pull_request(payload))
    assert result.get("pending") == "installation not bound to workspace"
