"""Unit tests for patch validator."""

import asyncio
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.validator import validate

FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "test-agent"
    / "fixtures"
    / "refund_agent.buggy.py"
)


def _run(coro):
    return asyncio.run(coro)


def test_validate_empty_diff_fails():
    result = _run(validate("", "foo.py", source_text="x = 1\n"))
    assert not result.valid
    assert any("empty" in e.lower() for e in result.errors)


def test_validate_valid_simple_diff():
    source = "def foo():\n    return 1\n"
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,2 @@
 def foo():
-    return 1
+    return 2
"""
    result = _run(validate(diff, "foo.py", source_text=source))
    assert result.valid
    assert result.patched_source is not None
    assert "return 2" in result.patched_source


def test_validate_stale_diff_fails():
    source = FIXTURE.read_text(encoding="utf-8")
    diff = """--- a/src/refund_agent.py
+++ b/src/refund_agent.py
@@ -1,3 +1,3 @@
 import time
-
+import os
"""
    result = _run(validate(diff, str(FIXTURE), source_text=source))
    assert not result.valid
