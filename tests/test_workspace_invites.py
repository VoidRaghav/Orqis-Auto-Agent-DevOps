"""Workspace invite flow tests."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration
from fastapi.testclient import TestClient

from orqis import config
from orqis.backend.server import app
from tests.tenancy_helpers import clear_workspace_sync, redis_available, session_cookies


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
    monkeypatch.setattr(config, "SESSION_SECRET", "test-session-secret-32-characters-minimum")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    monkeypatch.setattr(config, "GITHUB_OAUTH_CLIENT_ID", "test-oauth-id")
    monkeypatch.setattr(config, "GITHUB_OAUTH_CLIENT_SECRET", "test-oauth-secret")
    monkeypatch.setattr(config, "GITHUB_APP_ID", "")


@pytest.fixture
def client(mt_env, redis_ready):
    with TestClient(app) as c:
        yield c


def test_owner_can_create_invite_and_preview(client):
    ws = f"inv_owner_{uuid.uuid4().hex[:8]}"
    cookies = session_cookies(ws, login="owner")

    create = client.post("/workspace/invites", cookies=cookies)
    assert create.status_code == 200
    data = create.json()
    token = data["token"]
    assert token

    preview = client.get(f"/invites/{token}/preview")
    assert preview.status_code == 200
    assert preview.json()["workspace_id"] == ws

    members = client.get("/workspace/members", cookies=cookies)
    assert members.status_code == 200
    assert any(m["role"] == "owner" for m in members.json())

    client.delete(f"/workspace/invites/{token}", cookies=cookies)
    clear_workspace_sync(ws)


def test_non_owner_cannot_create_invite(client):
    ws = f"inv_member_{uuid.uuid4().hex[:8]}"
    owner_cookies = session_cookies(ws, login="owner", github_id=100)
    create = client.post("/workspace/invites", cookies=owner_cookies)
    assert create.status_code == 200

    import json
    from datetime import datetime, timezone

    from tests.tenancy_helpers import sync_redis

    member_id = 200
    r = sync_redis()
    r.hset(
        f"orqis:workspace:{ws}:members",
        str(member_id),
        json.dumps(
            {
                "github_id": member_id,
                "login": "member",
                "role": "member",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )
    member_cookies = session_cookies(ws, login="member", github_id=member_id)

    denied = client.post("/workspace/invites", cookies=member_cookies)
    assert denied.status_code == 403

    clear_workspace_sync(ws)
