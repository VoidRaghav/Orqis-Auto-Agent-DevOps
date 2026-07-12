"""Workspace isolation — incidents in workspace A must not appear in workspace B."""

from __future__ import annotations

import uuid

import pytest

from tests.tenancy_helpers import (
    clear_workspace_sync,
    get_incident_sync,
    get_settings_sync,
    list_incident_ids_sync,
    redis_available,
    save_settings_sync,
    seed_incident_sync,
)


@pytest.fixture
def redis_required():
    if not redis_available():
        pytest.skip("Redis not available")


@pytest.mark.usefixtures("redis_required")
def test_incidents_isolated_by_workspace_prefix():
    a = f"test_ws_a_{uuid.uuid4().hex[:8]}"
    b = f"test_ws_b_{uuid.uuid4().hex[:8]}"
    inc_id = str(uuid.uuid4())
    seed_incident_sync(a, inc_id, "isolation probe A")

    assert get_incident_sync(b, inc_id) is None
    assert inc_id not in list_incident_ids_sync(b)

    found = get_incident_sync(a, inc_id)
    assert found is not None
    assert found.error_message == "isolation probe A"

    clear_workspace_sync(a)


@pytest.mark.usefixtures("redis_required")
def test_settings_isolated_per_workspace():
    a, b = "set_a_iso", "set_b_iso"
    save_settings_sync(a, {"default_repo": "org/a-repo"})

    assert get_settings_sync(b).get("default_repo") != "org/a-repo"
    save_settings_sync(b, {"default_repo": "org/b-repo"})
    assert get_settings_sync(b).get("default_repo") == "org/b-repo"
    assert get_settings_sync(a).get("default_repo") == "org/a-repo"

    clear_workspace_sync(a)
    clear_workspace_sync(b)
