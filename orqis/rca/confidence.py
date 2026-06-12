"""
Patch confidence scoring (0–100).

Each signal is independent and additive. The thresholds were tuned against
the small Spline of fixtures in tests/ — they are conservative on purpose:
better to surface a "low-confidence" patch than to silently auto-apply
something risky.

Signals:
  +30  validation passed (no errors)
  +15  ruff clean
  +25  diff touches the exact error line from the traceback
  +20  total changes ≤ 5 lines
  +12  total changes 6–12 lines
  +5   total changes 13–25 lines
  +10  no new imports introduced

Above THRESHOLD → PATCHED.
Below THRESHOLD → LOW_CONFIDENCE (human-review only, no auto-apply).
"""

import re
from typing import Optional

from .file_reader import CodeLocation
from .validator import ValidationResult


THRESHOLD = 50


_HUNK_RANGE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+", re.MULTILINE)


def score(
    diff: str,
    location: Optional[CodeLocation],
    validation: ValidationResult,
) -> int:
    if not validation.valid:
        return 0

    pts = 30  # validation passed

    ruff_issues = sum(1 for e in validation.errors if e.startswith("ruff:"))
    if ruff_issues == 0:
        pts += 15
    elif ruff_issues == 1:
        pts += 8

    if location and _touches_line(diff, location.line):
        pts += 25

    added, removed = _diff_size(diff)
    changes = added + removed
    if changes <= 5:
        pts += 20
    elif changes <= 12:
        pts += 12
    elif changes <= 25:
        pts += 5

    has_new_imports = any(
        "introduces new imports" in w for w in validation.warnings
    )
    if not has_new_imports:
        pts += 10

    return max(0, min(100, pts))


def _touches_line(diff: str, target_line: int) -> bool:
    for m in _HUNK_RANGE.finditer(diff):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) else 1
        if start <= target_line <= start + count:
            return True
    return False


def _diff_size(diff: str) -> tuple[int, int]:
    added = removed = 0
    for line in diff.splitlines():
        if not line or line[0] not in ("+", "-"):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed
