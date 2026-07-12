"""Split a unified diff into per-file segments."""

from __future__ import annotations

import re

_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def split_by_file(diff: str) -> list[tuple[str, str]]:
    if not diff or not diff.strip():
        return []
    paths = _FILE_HEADER.findall(diff)
    if len(paths) <= 1:
        path = paths[0] if paths else "unknown"
        return [(path, diff)]
    chunks: list[tuple[str, str]] = []
    parts = re.split(r"(?=^--- a/)", diff, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = _FILE_HEADER.search(part)
        if m:
            chunks.append((m.group(1).strip(), part + "\n"))
    return chunks
