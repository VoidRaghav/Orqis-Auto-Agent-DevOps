"""Unit tests for is_auto_merge_eligible path scoping."""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

from orqis.backend.models import IncidentStatus, ValidationStatus
from orqis.integrations.github.pr_service import is_auto_merge_eligible


def _incident(**kwargs):
    base = dict(
        fix_method="deterministic",
        validation_status=ValidationStatus.PASSED,
        repo_relative_path="config/app.toml",
        status=IncidentStatus.PR_OPEN,
    )
    base.update(kwargs)
    # Minimal stand-in — only fields is_auto_merge_eligible reads.
    return SimpleNamespace(**base)


def test_auto_merge_eligible_config_toml():
    assert is_auto_merge_eligible(_incident(), {"auto_merge_enabled": True}) is True


def test_auto_merge_rejects_github_workflow_yml():
    inc = _incident(repo_relative_path=".github/workflows/ci.yml")
    assert is_auto_merge_eligible(inc, {"auto_merge_enabled": True}) is False


def test_auto_merge_rejects_traversal():
    inc = _incident(repo_relative_path="../secrets.toml")
    assert is_auto_merge_eligible(inc, {"auto_merge_enabled": True}) is False


def test_auto_merge_off_when_disabled():
    assert is_auto_merge_eligible(_incident(), {"auto_merge_enabled": False}) is False
