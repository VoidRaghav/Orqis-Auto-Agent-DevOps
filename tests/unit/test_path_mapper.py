"""Unit tests for path_mapper."""

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.path_mapper import best_tree_match, to_repo_relative


def test_to_repo_relative_strips_app_prefix():
    assert to_repo_relative("/app/src/refund_agent.py") == "src/refund_agent.py"


def test_to_repo_relative_strips_render_prefix():
    assert to_repo_relative("/opt/render/project/src/demo/service.py") == "demo/service.py"


def test_to_repo_relative_already_relative():
    assert to_repo_relative("demo/service.py") == "demo/service.py"


def test_to_repo_relative_site_packages_returns_none():
    assert to_repo_relative("/usr/lib/python3.11/site-packages/foo/bar.py") is None


def test_to_repo_relative_frozen_returns_none():
    assert to_repo_relative("<frozen importlib._bootstrap>") is None


def test_best_tree_match_exact():
    tree = {"src/refund_agent.py", "src/payment.py"}
    assert best_tree_match("src/refund_agent.py", tree) == "src/refund_agent.py"


def test_best_tree_match_suffix():
    tree = {"src/refund_agent.py", "src/payment.py"}
    assert best_tree_match("app/src/refund_agent.py", tree) == "src/refund_agent.py"


def test_best_tree_match_unique_basename():
    tree = {"src/refund_agent.py", "lib/other.py"}
    assert best_tree_match("refund_agent.py", tree) == "src/refund_agent.py"


def test_best_tree_match_ambiguous_basename():
    tree = {"a/foo.py", "b/foo.py"}
    assert best_tree_match("foo.py", tree) is None
