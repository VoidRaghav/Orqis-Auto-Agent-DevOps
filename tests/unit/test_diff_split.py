"""Unit tests for multi-file diff split."""

import pytest

pytestmark = pytest.mark.unit

from orqis.rca.diff_split import split_by_file


def test_split_by_file_single():
    diff = """--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,1 @@
-x
+y
"""
    parts = split_by_file(diff)
    assert len(parts) == 1
    assert parts[0][0] == "foo.py"


def test_split_by_file_multi():
    diff = """--- a/src/a.py
+++ b/src/a.py
@@ -1,1 +1,1 @@
-x
+y
--- a/src/b.py
+++ b/src/b.py
@@ -1,1 +1,1 @@
-a
+b
"""
    parts = split_by_file(diff)
    assert len(parts) == 2
    paths = {p for p, _ in parts}
    assert paths == {"src/a.py", "src/b.py"}
