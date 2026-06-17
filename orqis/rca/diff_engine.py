"""
Shared unified-diff parser and applier (H1).

Single implementation used by the validator, GitHub in-memory applier, and the
local disk fallback so hunk logic cannot drift between code paths.
"""

import re
from typing import Optional

_HUNK_HEADER = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


class DiffApplyError(Exception):
    """Base error for diff application failures."""


class StaleDiffError(DiffApplyError):
    """The diff does not apply cleanly to the given source text."""


def parse_hunks(diff: str) -> list[tuple[int, list[str]]]:
    """Return (old_start_line, body_lines) for each hunk, skipping file headers."""
    lines = diff.splitlines()
    hunks: list[tuple[int, list[str]]] = []
    i = 0
    while i < len(lines):
        m = _HUNK_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))
        i += 1
        body: list[str] = []
        while i < len(lines):
            line = lines[i]
            if _HUNK_HEADER.match(line) or line.startswith("---") or line.startswith("+++"):
                break
            if not line or line[0] in (" ", "+", "-", "\\"):
                body.append(line)
            i += 1
        hunks.append((old_start, body))
    return hunks


def apply_hunks(source: str, hunks: list[tuple[int, list[str]]]) -> str:
    """
    Apply parsed hunks to `source`. Verifies every context and removal line.
    Preserves a trailing newline when the source had one.
    """
    if not hunks:
        raise StaleDiffError("no parseable hunks in diff")

    src = source.splitlines()
    out: list[str] = []
    idx = 0

    for old_start, body in hunks:
        target = old_start - 1
        if target < idx:
            raise StaleDiffError(f"hunks out of order at line {old_start}")
        if target > len(src):
            raise StaleDiffError(f"hunk start line {old_start} past end of file")

        out.extend(src[idx:target])
        idx = target

        for line in body:
            if not line:
                continue
            tag = line[0]
            payload = line[1:]
            if tag == " ":
                if idx >= len(src) or src[idx] != payload:
                    raise StaleDiffError(
                        f"context mismatch at line {idx + 1} — base content drifted"
                    )
                out.append(payload)
                idx += 1
            elif tag == "-":
                if idx >= len(src) or src[idx] != payload:
                    raise StaleDiffError(
                        f"stale removal at line {idx + 1} — base content drifted"
                    )
                idx += 1
            elif tag == "+":
                out.append(payload)

    out.extend(src[idx:])
    text = "\n".join(out)
    if source.endswith("\n"):
        text += "\n"
    return text


def apply_to_text(source: str, diff: str) -> str:
    """Parse `diff` and apply it to `source`."""
    if not diff or not diff.strip():
        raise StaleDiffError("empty diff")
    return apply_hunks(source, parse_hunks(diff))


def rewrite_diff_paths(diff: str, repo_relative_path: str) -> str:
    """Rewrite ---/+++ headers to use the repo-relative path (R2)."""
    out: list[str] = []
    for line in diff.splitlines():
        if line.startswith("--- "):
            out.append(f"--- a/{repo_relative_path}")
        elif line.startswith("+++ "):
            out.append(f"+++ b/{repo_relative_path}")
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if diff.endswith("\n") else "")


def changed_path(diff: str) -> Optional[str]:
    """Extract the repo-relative target path from the +++ header."""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].strip().split("\t")[0]
            for prefix in ("b/", "a/"):
                if raw.startswith(prefix):
                    raw = raw[len(prefix):]
            return raw or None
    return None
