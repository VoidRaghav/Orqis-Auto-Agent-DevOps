"""Unit tests for secret scan."""

import pytest

pytestmark = pytest.mark.unit

from orqis.integrations.github.pr_service import scan_for_secrets, sanitize


def test_scan_for_secrets_aws_key():
    diff = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    hits = scan_for_secrets(diff)
    assert len(hits) >= 1


def test_scan_clean_diff():
    assert scan_for_secrets("def foo():\n    return 1\n") == []
