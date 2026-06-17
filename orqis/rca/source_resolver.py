"""
GitHub source resolution for RCA (A2 / R1).

When Orqis runs on a server (Railway) it cannot read the failing file off the
local filesystem — the code lives in the user's GitHub repo, not on the Orqis
host. This module bridges that gap:

  1. Resolve the incident's `source` label to an `owner/repo` via workspace
     settings (source_repo_map).
  2. Parse the traceback frames and walk them innermost-first.
  3. For each frame, map the deploy path to a repo-relative path and confirm it
     exists in the repo tree (skips third-party/library frames — R1).
  4. Fetch that file's content at the default-branch HEAD.
  5. Build a CodeLocation carrying the fetched source_text + repo_relative_path
     so the patch/validate/commit steps operate entirely in memory (R2).

Returns None whenever GitHub isn't configured, the source isn't mapped, or no
frame resolves to a real repo file — the caller then degrades to the existing
local-filesystem path (dev) or interpretation-only (prod, no repo).
"""

from dataclasses import dataclass
from typing import Optional

from ..backend import store
from ..integrations.github import auth, client
from . import file_reader, path_mapper


@dataclass
class ResolvedSource:
    repo_full_name: str
    installation_id: int
    base_branch: str
    base_sha: str
    repo_relative_path: str
    location: "file_reader.CodeLocation"


def repo_for_source(settings: dict, source: str) -> Optional[str]:
    """
    Map an incident source label to an owner/repo.

    Tries the explicit source_repo_map first, then falls back to a single
    connected repo when exactly one is available (zero-config common case).
    """
    mapping = settings.get("source_repo_map") or {}
    if source in mapping:
        return mapping[source]
    # "sentry:project" style sources — try the bare project name too.
    if ":" in source:
        tail = source.split(":", 1)[1]
        if tail in mapping:
            return mapping[tail]
    repos = settings.get("repos") or []
    if len(repos) == 1:
        return repos[0]
    return None


async def resolve(error_text: str, source: str) -> Optional[ResolvedSource]:
    """
    Resolve a traceback to a fetched GitHub source location, or None.
    Never raises — any failure returns None so RCA degrades gracefully.
    """
    frames = file_reader.parse_frames(error_text)
    if not frames:
        return None
    return await _resolve_frames(frames, source)


async def resolve_file(source: str, raw_path: str, line: int) -> Optional[ResolvedSource]:
    """
    Resolve a single known (path, line) to GitHub source — used by the anomaly
    path, which knows the looping call site directly and has no traceback.
    """
    if not raw_path or line <= 0:
        return None
    return await _resolve_frames([(raw_path, line)], source)


async def _resolve_frames(
    frames: list[tuple[str, int]], source: str
) -> Optional[ResolvedSource]:
    if not auth.is_configured():
        return None

    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        return None

    repo = repo_for_source(settings, source)
    if not repo:
        return None

    if not await client.repo_accessible(installation_id, repo):
        return None

    default = await client.get_default_branch(installation_id, repo)
    if default is None:
        return None
    base_branch, base_sha = default

    tree = await client.get_repo_tree(installation_id, repo, base_sha)
    if not tree:
        return None

    # Walk innermost-first: the deepest repo-owned frame is where the fix goes.
    for raw_path, line in reversed(frames):
        repo_rel = path_mapper.to_repo_relative(raw_path)
        if repo_rel is None:
            continue
        matched = path_mapper.best_tree_match(repo_rel, tree)
        if matched is None:
            continue  # third-party / not in repo (R1)

        fetched = await client.get_file(installation_id, repo, matched, base_sha)
        if fetched is None:
            continue
        content, _blob_sha = fetched

        location = file_reader.location_from_source(
            content, raw_path, line, repo_relative_path=matched
        )
        if location is None:
            continue

        return ResolvedSource(
            repo_full_name=repo,
            installation_id=installation_id,
            base_branch=base_branch,
            base_sha=base_sha,
            repo_relative_path=matched,
            location=location,
        )

    return None
