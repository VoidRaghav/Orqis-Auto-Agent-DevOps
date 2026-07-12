"""Unit tests for workspace tenancy helpers."""

import pytest

pytestmark = pytest.mark.unit

from orqis.backend.tenancy import (
    DEFAULT_WORKSPACE_ID,
    get_workspace_id,
    reset_workspace_id,
    set_workspace_id,
    tenant_prefix,
)
from orqis.integrations.github import install_state


def test_tenant_prefix_default():
    assert tenant_prefix() == f"orqis:t:{DEFAULT_WORKSPACE_ID}:"


def test_tenant_prefix_explicit():
    assert tenant_prefix("abc123") == "orqis:t:abc123:"


def test_workspace_context():
    tok = set_workspace_id("ws_test")
    try:
        assert get_workspace_id() == "ws_test"
        assert tenant_prefix() == "orqis:t:ws_test:"
    finally:
        reset_workspace_id(tok)


def test_install_state_roundtrip():
    wid = "workspace_abc"
    state = install_state.create_state(wid)
    assert install_state.verify_state(state)
    assert install_state.parse_state(state) == wid
