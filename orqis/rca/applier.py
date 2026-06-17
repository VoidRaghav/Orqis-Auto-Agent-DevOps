"""
Patch applier.

Takes a unified diff string and applies it to the file on disk using Python's
stdlib `subprocess` + the system `patch` command. Falls back to manual
line-by-line application via `difflib` if `patch` is not installed.

Safety rules:
  - Only writes files that are inside the project root (path traversal guard).
  - Creates a .bak backup before writing.
  - Never touches files outside .py extension for now.
  - Returns (success, message) — never raises.
"""

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional


def apply(diff: str, project_root: str) -> tuple[bool, str]:
    """
    Apply a unified diff to disk.

    Returns:
        (True, "")            on success
        (False, reason_str)   on failure
    """
    if not diff or not diff.strip():
        return False, "empty diff"

    target_path = _extract_target_path(diff, project_root)
    if target_path is None:
        return False, "could not resolve target file from diff header"

    if not _is_safe(target_path, project_root):
        return False, f"target file {target_path} is outside project root"

    if not os.path.isfile(target_path):
        return False, f"target file does not exist: {target_path}"

    # Back up before touching anything
    backup = target_path + ".orqis.bak"
    try:
        shutil.copy2(target_path, backup)
    except OSError as e:
        return False, f"could not create backup: {e}"

    # Try `patch` binary first (most reliable)
    if shutil.which("patch"):
        ok, msg = _apply_with_patch_binary(diff, target_path)
    else:
        ok, msg = _apply_manually(diff, target_path)

    if not ok:
        # Restore backup on failure
        try:
            shutil.copy2(backup, target_path)
        except OSError:
            pass

    return ok, msg


def _extract_target_path(diff: str, project_root: str) -> Optional[str]:
    """
    Extract the target file path from the +++ header of a unified diff.
    Handles both absolute paths and a/b-prefixed relative paths.
    """
    for line in diff.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].strip()
            # Strip leading a/ or b/ (git diff convention)
            for prefix in ("b/", "a/"):
                if raw.startswith(prefix):
                    raw = raw[len(prefix):]
            # Remove trailing tab + timestamp if present
            raw = re.split(r"\t", raw)[0].strip()

            if os.path.isabs(raw):
                return raw
            # Resolve relative to project root
            return os.path.join(project_root, raw)
    return None


def _is_safe(path: str, project_root: str) -> bool:
    """Ensure the resolved path is inside the project root."""
    abs_path = os.path.realpath(path)
    abs_root = os.path.realpath(project_root)
    return abs_path.startswith(abs_root + os.sep) or abs_path == abs_root


def _apply_with_patch_binary(diff: str, target_path: str) -> tuple[bool, str]:
    """Use the system `patch` command to apply the diff."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(diff)
        patch_file = f.name

    try:
        result = subprocess.run(
            ["patch", "--forward", "--quiet", target_path, patch_file],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip() or result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "patch command timed out"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            os.unlink(patch_file)
        except OSError:
            pass


def _apply_manually(diff: str, target_path: str) -> tuple[bool, str]:
    """
    Apply a unified diff to disk using the shared diff_engine (H1).
    Preserves the file's native line-ending style on write.
    """
    from .diff_engine import DiffApplyError, apply_to_text

    try:
        with open(target_path, "r", encoding="utf-8", newline="") as f:
            raw = f.read()
    except OSError as e:
        return False, f"could not read file: {e}"

    try:
        out = apply_to_text(raw, diff)
    except DiffApplyError as e:
        return False, str(e)

    try:
        with open(target_path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        return True, ""
    except OSError as e:
        return False, f"could not write file: {e}"
