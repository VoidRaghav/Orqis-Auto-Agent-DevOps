"""Unit tests for diff_engine."""

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.diff_engine import (
    StaleDiffError,
    apply_to_text,
    changed_path,
    parse_hunks,
    rewrite_diff_paths,
)


SAMPLE_SOURCE = """def hello():
    x = 1
    return x
"""


def test_parse_hunks_single():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 def hello():
-    x = 1
+    x = 2
     return x
"""
    hunks = parse_hunks(diff)
    assert len(hunks) == 1
    assert hunks[0][0] == 1
    assert any("-    x = 1" in line for line in hunks[0][1])


def test_apply_to_text_success():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 def hello():
-    x = 1
+    x = 2
     return x
"""
    result = apply_to_text(SAMPLE_SOURCE, diff)
    assert "x = 2" in result
    assert "x = 1" not in result


def test_apply_to_text_stale_raises():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 def hello():
-    x = 999
+    x = 2
     return x
"""
    with pytest.raises(StaleDiffError):
        apply_to_text(SAMPLE_SOURCE, diff)


def test_rewrite_diff_paths():
    diff = "--- old\n+++ old\n"
    out = rewrite_diff_paths(diff, "src/foo.py")
    assert "--- a/src/foo.py" in out
    assert "+++ b/src/foo.py" in out


def test_changed_path():
    diff = """--- a/src/foo.py
+++ b/src/foo.py
@@ -1,1 +1,1 @@
"""
    assert changed_path(diff) == "src/foo.py"
