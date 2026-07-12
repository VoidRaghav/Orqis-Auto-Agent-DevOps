"""Unit tests for PR body sanitization."""

import pytest

pytestmark = pytest.mark.unit

from orqis.integrations.github.pr_service import sanitize


def test_sanitize_api_key():
    text = "api_key=supersecret123"
    out = sanitize(text)
    assert "supersecret123" not in out
    assert "[REDACTED]" in out


def test_sanitize_bearer_token():
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc"
    out = sanitize(text)
    assert "eyJhbGci" not in out


def test_sanitize_sk_prefix():
    text = "key is sk-abcdefghijklmnopqrst"
    out = sanitize(text)
    assert "sk-abcdefghijklmnopqrst" not in out


def test_sanitize_empty_passthrough():
    assert sanitize("") == ""
