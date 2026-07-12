"""Unit tests for deterministic remediation."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.file_reader import CodeLocation
from orqis.rca.remediation import MAX_ATTEMPTS, guard_runaway_loop

FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "test-agent"
    / "fixtures"
    / "refund_agent.buggy.py"
)


def _location(source: str) -> CodeLocation:
    return CodeLocation(
        file_path=str(FIXTURE),
        line=11,
        function_name="resolve_refund",
        context="",
        context_start_line=9,
        source_text=source,
        repo_relative_path="src/refund_agent.py",
    )


def test_guard_runaway_loop_produces_diff():
    source = FIXTURE.read_text(encoding="utf-8")
    diff = guard_runaway_loop(_location(source))
    assert diff is not None
    assert str(MAX_ATTEMPTS) in diff
    assert "while status ==" in diff or "+    if" in diff


def test_guard_runaway_loop_no_while_returns_none():
    source = "def foo():\n    return 1\n"
    assert guard_runaway_loop(_location(source)) is None


def test_guard_runaway_loop_no_function_name_returns_none():
    source = FIXTURE.read_text(encoding="utf-8")
    loc = _location(source)
    loc.function_name = None
    assert guard_runaway_loop(loc) is None
