"""Per-repo default branch resolution."""

from __future__ import annotations

from typing import Optional


def resolve_base_branch(settings: dict, repo: str) -> Optional[str]:
    """
    Order: per-repo map → workspace global default → None (GitHub API default).
    """
    branches = settings.get("repo_default_branches") or {}
    if repo in branches and branches[repo]:
        return branches[repo]
    global_default = settings.get("default_branch") or ""
    return global_default or None
