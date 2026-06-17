"""
In-memory unified-diff applier for the GitHub PR path.

Delegates hunk parsing and application to the shared diff_engine module (H1).
"""

from ...rca.diff_engine import (
    DiffApplyError,
    StaleDiffError,
    apply_to_text,
    changed_path,
    rewrite_diff_paths,
)

__all__ = [
    "DiffApplyError",
    "StaleDiffError",
    "apply_to_text",
    "changed_path",
    "rewrite_diff_paths",
]
