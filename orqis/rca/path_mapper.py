"""
Deploy-path -> repo-relative path normalization (A1).

A production traceback reports the path as it exists on the deploy host, e.g.
`/app/demo/service.py` on Railway or `/opt/render/project/src/demo/service.py`
on Render. The GitHub repo stores the same file as `demo/service.py`. Before we
can read or patch the file through the GitHub API we must strip the deploy
prefix and recover the repo-relative path.

There is no universal rule, so we:
  1. Strip a set of well-known deploy/runtime prefixes.
  2. Drop everything up to and including a leading `site-packages/` segment
     (those frames are third-party and never belong to the user's repo).
  3. Fall back to matching a suffix of the path against the repo tree
     (handled by source_resolver, which knows the actual file list).
"""

import posixpath
from typing import Optional

# Common deploy roots, longest first so the most specific match wins.
_DEPLOY_PREFIXES = (
    "/opt/render/project/src/",
    "/home/site/wwwroot/",
    "/workspace/",
    "/usr/src/app/",
    "/app/",
    "/code/",
    "/srv/",
)


def to_repo_relative(raw_path: str) -> Optional[str]:
    """
    Best-effort conversion of an absolute deploy path to a repo-relative path.
    Returns None for paths that clearly belong to the runtime / stdlib /
    third-party packages (which can never be in the user's repo).
    """
    if not raw_path:
        return None

    # Normalize Windows separators so the logic is single-codepath.
    path = raw_path.replace("\\", "/")

    # Frames inside installed dependencies or the stdlib are never repo files.
    lowered = path.lower()
    for marker in ("/site-packages/", "/dist-packages/", "/lib/python", "<frozen", "<string>"):
        if marker in lowered:
            return None

    for prefix in _DEPLOY_PREFIXES:
        if path.startswith(prefix):
            return _clean(path[len(prefix):])

    if not path.startswith("/"):
        # Already relative (e.g. "demo/service.py") — just clean it.
        return _clean(path)

    # Absolute but no known prefix — return the tail without the leading slash so
    # source_resolver can still try a suffix match against the repo tree.
    return _clean(path.lstrip("/"))


def _clean(rel: str) -> Optional[str]:
    rel = posixpath.normpath(rel).lstrip("./")
    if not rel or rel.startswith(".."):
        return None
    return rel


def best_tree_match(repo_relative: str, tree_paths: set) -> Optional[str]:
    """
    Match a (possibly imperfect) repo-relative path against the real repo tree.

    Tries an exact hit first, then progressively shorter path suffixes so a
    monorepo subdir or an unexpected deploy prefix still resolves. Returns the
    matching repo path, or None when the file is not in the repo (R1 — skip).
    """
    if not repo_relative or not tree_paths:
        return None

    if repo_relative in tree_paths:
        return repo_relative

    parts = repo_relative.split("/")
    # Try suffixes: a/b/c.py -> b/c.py -> c.py
    for start in range(1, len(parts)):
        suffix = "/".join(parts[start:])
        if suffix in tree_paths:
            return suffix

    # Last resort: unique basename match.
    base = parts[-1]
    matches = [p for p in tree_paths if p.split("/")[-1] == base]
    if len(matches) == 1:
        return matches[0]
    return None
