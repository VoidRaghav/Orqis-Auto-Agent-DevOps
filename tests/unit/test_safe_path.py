"""Unit tests for repo path sanitization / auto-merge path gates."""

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.safe_path import (
    is_auto_merge_path_allowed,
    is_blocked_write_path,
    normalize_repo_path,
    validate_commit_paths,
)


def test_normalize_accepts_relative():
    assert normalize_repo_path("src/refund_agent.py") == "src/refund_agent.py"
    assert normalize_repo_path("./src/foo.py") == "src/foo.py"
    assert normalize_repo_path(r"src\foo.py") == "src/foo.py"


def test_normalize_rejects_traversal_and_absolute():
    assert normalize_repo_path("../etc/passwd") is None
    assert normalize_repo_path("src/../../etc/passwd") is None
    assert normalize_repo_path("/etc/passwd") is None
    assert normalize_repo_path("C:/Windows/system32") is None
    assert normalize_repo_path("") is None
    assert normalize_repo_path("a\x00b") is None


def test_blocked_write_github_workflows():
    assert is_blocked_write_path(".github/workflows/ci.yml") is True
    assert is_blocked_write_path(".git/config") is True
    assert is_blocked_write_path("src/app.py") is False


def test_validate_commit_paths():
    assert validate_commit_paths(["src/a.py", "cfg/railway.toml"]) is None
    err = validate_commit_paths([".github/workflows/ci.yml"])
    assert err is not None and "blocked" in err
    err2 = validate_commit_paths(["../secret.py"])
    assert err2 is not None and "unsafe" in err2


def test_auto_merge_blocks_ci_even_with_yml_suffix():
    assert is_auto_merge_path_allowed(".github/workflows/deploy.yml") is False
    assert is_auto_merge_path_allowed("Dockerfile") is False
    assert is_auto_merge_path_allowed("docker-compose.yml") is False
    assert is_auto_merge_path_allowed("config/app.toml") is True
    assert is_auto_merge_path_allowed(".env.example") is True
    assert is_auto_merge_path_allowed(".env") is False
