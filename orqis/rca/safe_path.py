"""Repo-relative path validation for GitHub write / auto-merge paths.

Rejects traversal, absolute paths, and sensitive trees (.git, .github) before
any Contents/git API call or auto-merge decision.
"""

from __future__ import annotations

import posixpath
from typing import Optional

# Never write via Orqis PR automation (CI/CD + git metadata).
_BLOCKED_WRITE_PREFIXES = (
    ".git/",
    ".github/",
)

# Never auto-merge even if basename matches a config suffix (.yml/.toml/…).
_AUTO_MERGE_DENY_BASENAMES = frozenset(
    {
        "jenkinsfile",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        ".gitlab-ci.yml",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        "buildkite.yml",
        "cloudbuild.yaml",
        "cloudbuild.yml",
        "package.json",
        "package-lock.json",
    }
)


def normalize_repo_path(path: str) -> Optional[str]:
    """Return a clean forward-slash relative path, or None if unsafe.

    Rejects empty paths, NUL bytes, absolute paths, Windows drive paths,
    and any ``..`` segment after posix normalization.
    """
    if path is None:
        return None
    raw = str(path).strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        return None
    # Strip accidental leading "./"
    while raw.startswith("./"):
        raw = raw[2:]
    if not raw or raw in (".", "/"):
        return None
    if raw.startswith("/") or raw.startswith("~"):
        return None
    # Windows absolute / UNC
    if len(raw) >= 2 and raw[1] == ":":
        return None
    if raw.startswith("//"):
        return None
    normalized = posixpath.normpath(raw)
    if normalized in (".", "..") or normalized.startswith("../"):
        return None
    if normalized.startswith("/") or ".." in normalized.split("/"):
        return None
    # normpath can collapse to empty on odd inputs
    if not normalized or normalized == ".":
        return None
    return normalized


def is_blocked_write_path(path: str) -> bool:
    """True if Orqis must not commit this path via the GitHub write API."""
    cleaned = normalize_repo_path(path)
    if cleaned is None:
        return True
    lower = cleaned.lower()
    if lower == ".git" or lower.startswith(".git/"):
        return True
    if lower == ".github" or lower.startswith(".github/"):
        return True
    for prefix in _BLOCKED_WRITE_PREFIXES:
        if lower.startswith(prefix):
            return True
    return False


def is_auto_merge_path_allowed(path: str) -> bool:
    """Stricter gate for unattended squash-merge to the default branch."""
    cleaned = normalize_repo_path(path)
    if cleaned is None or is_blocked_write_path(cleaned):
        return False
    basename = cleaned.split("/")[-1].lower()
    if basename in _AUTO_MERGE_DENY_BASENAMES:
        return False
    # Leading-dot paths except exact allowlist handled by caller
    # (e.g. .env.example). Block other hidden paths from auto-merge.
    if basename.startswith(".") and basename not in {".env.example"}:
        return False
    return True


def validate_commit_paths(paths: list[str]) -> Optional[str]:
    """Return an error string if any path is unsafe for commit, else None."""
    if not paths:
        return "no file paths to commit"
    for path in paths:
        cleaned = normalize_repo_path(path)
        if cleaned is None:
            return f"unsafe repo path rejected: {path!r}"
        if is_blocked_write_path(cleaned):
            return f"blocked path (refusing write): {cleaned}"
    return None
