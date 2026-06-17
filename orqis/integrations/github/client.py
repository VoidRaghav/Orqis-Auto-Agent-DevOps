"""
Thin async GitHub REST client used by the PR-first fix flow.

Every method takes the installation_id and resolves a scoped token via auth.py.
All methods return None / empty / (False, reason) on failure and never raise —
the pipeline degrades to interpretation-only when GitHub is unreachable.

Covers exactly what the fix flow needs:
  - repo_accessible   : guard before any write
  - get_repo_tree     : cached recursive tree (repo-frame guard, R1)
  - get_default_branch: base branch + HEAD sha
  - get_file          : Contents API read (1MB cap, G1)
  - create_branch     : Git Data API ref create (collision retry, G2)
  - commit_file       : blob -> tree -> commit -> update branch ref (A3)
  - open_pull_request : Pulls API
  - close_pull_request / merge_pull_request / delete_branch / get_pull_request
"""

import base64
import time
from typing import Optional

import httpx

from . import auth

_GITHUB_API = "https://api.github.com"
_CONTENTS_MAX_BYTES = 1_000_000  # GitHub Contents API returns base64 up to ~1MB (G1)

# (installation_id, repo) -> (set_of_paths, fetched_at_unix)
_tree_cache: dict[tuple[int, str], tuple[set, float]] = {}
_TREE_TTL_S = 300.0


async def _headers(installation_id: int) -> Optional[dict]:
    token = await auth.installation_token(installation_id)
    if token is None:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def repo_accessible(installation_id: int, repo: str) -> bool:
    """G3 — verify the installation can actually reach this repo before writing."""
    headers = await _headers(installation_id)
    if headers is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(f"{_GITHUB_API}/repos/{repo}", headers=headers)
            return resp.status_code == 200
    except Exception:
        return False


async def get_default_branch(
    installation_id: int, repo: str, branch: Optional[str] = None
) -> Optional[tuple[str, str]]:
    """Return (branch_name, head_commit_sha) or None."""
    headers = await _headers(installation_id)
    if headers is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            if not branch:
                r = await http.get(f"{_GITHUB_API}/repos/{repo}", headers=headers)
                r.raise_for_status()
                branch = r.json().get("default_branch", "main")
            ref = await http.get(
                f"{_GITHUB_API}/repos/{repo}/git/ref/heads/{branch}", headers=headers
            )
            ref.raise_for_status()
            sha = ref.json().get("object", {}).get("sha")
            if not sha:
                return None
            return branch, sha
    except Exception:
        return None


async def get_repo_tree(installation_id: int, repo: str, ref: str) -> set:
    """
    Return the set of repo-relative file paths at `ref` (recursive), cached.
    Used by the repo-frame guard (R1) to skip third-party/library frames.
    """
    cache_key = (installation_id, repo)
    cached = _tree_cache.get(cache_key)
    if cached and (time.time() - cached[1]) < _TREE_TTL_S:
        return cached[0]

    headers = await _headers(installation_id)
    if headers is None:
        return set()
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get(
                f"{_GITHUB_API}/repos/{repo}/git/trees/{ref}",
                headers=headers,
                params={"recursive": "1"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return set()

    paths = {
        entry["path"]
        for entry in data.get("tree", [])
        if entry.get("type") == "blob" and entry.get("path")
    }
    _tree_cache[cache_key] = (paths, time.time())
    return paths


async def get_file(
    installation_id: int, repo: str, path: str, ref: str
) -> Optional[tuple[str, str]]:
    """
    Read a file via the Contents API. Returns (text, blob_sha) or None.
    Skips files over the Contents API size cap (G1).
    """
    headers = await _headers(installation_id)
    if headers is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get(
                f"{_GITHUB_API}/repos/{repo}/contents/{path}",
                headers=headers,
                params={"ref": ref},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    if data.get("size", 0) > _CONTENTS_MAX_BYTES or data.get("encoding") != "base64":
        return None
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return None
    return text, data.get("sha", "")


async def create_branch(
    installation_id: int, repo: str, branch: str, from_sha: str
) -> Optional[str]:
    """
    Create branch ref pointing at from_sha. On collision (422), retry once with
    a timestamp suffix (G2). Returns the branch name actually created, or None.
    """
    headers = await _headers(installation_id)
    if headers is None:
        return None

    async def _try(name: str) -> Optional[int]:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(
                f"{_GITHUB_API}/repos/{repo}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{name}", "sha": from_sha},
            )
            return resp.status_code

    try:
        status = await _try(branch)
        if status == 201:
            return branch
        if status == 422:
            alt = f"{branch}-{int(time.time())}"
            if await _try(alt) == 201:
                return alt
    except Exception:
        return None
    return None


async def commit_file(
    installation_id: int,
    repo: str,
    branch: str,
    path: str,
    new_content: str,
    message: str,
    parent_sha: str,
) -> Optional[str]:
    """
    Commit a single file change onto `branch` using the Git Data API:
      blob -> tree (based on parent) -> commit -> update branch ref.
    Returns the new commit sha or None. Committer is the app bot (O3).
    """
    headers = await _headers(installation_id)
    if headers is None:
        return None

    bot_name = f"{config_slug()}[bot]" if config_slug() else "orqis[bot]"
    author = {"name": bot_name, "email": f"{bot_name}@users.noreply.github.com"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            blob = await http.post(
                f"{_GITHUB_API}/repos/{repo}/git/blobs",
                headers=headers,
                json={"content": new_content, "encoding": "utf-8"},
            )
            blob.raise_for_status()
            blob_sha = blob.json()["sha"]

            tree = await http.post(
                f"{_GITHUB_API}/repos/{repo}/git/trees",
                headers=headers,
                json={
                    "base_tree": parent_sha,
                    "tree": [
                        {"path": path, "mode": "100644", "type": "blob", "sha": blob_sha}
                    ],
                },
            )
            tree.raise_for_status()
            tree_sha = tree.json()["sha"]

            commit = await http.post(
                f"{_GITHUB_API}/repos/{repo}/git/commits",
                headers=headers,
                json={
                    "message": message,
                    "tree": tree_sha,
                    "parents": [parent_sha],
                    "author": author,
                    "committer": author,
                },
            )
            commit.raise_for_status()
            commit_sha = commit.json()["sha"]

            ref = await http.patch(
                f"{_GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
                headers=headers,
                json={"sha": commit_sha, "force": False},
            )
            ref.raise_for_status()
            return commit_sha
    except Exception:
        return None


async def open_pull_request(
    installation_id: int,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> Optional[tuple[int, str]]:
    """Open a PR. Returns (pr_number, html_url) or None."""
    headers = await _headers(installation_id)
    if headers is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.post(
                f"{_GITHUB_API}/repos/{repo}/pulls",
                headers=headers,
                json={"title": title, "head": head, "base": base, "body": body},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["number"], data["html_url"]
    except Exception:
        return None


async def get_pull_request(
    installation_id: int, repo: str, pr_number: int
) -> Optional[dict]:
    """Return the raw PR object (for poll fallback) or None."""
    headers = await _headers(installation_id)
    if headers is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(
                f"{_GITHUB_API}/repos/{repo}/pulls/{pr_number}", headers=headers
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def close_pull_request(installation_id: int, repo: str, pr_number: int) -> bool:
    headers = await _headers(installation_id)
    if headers is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.patch(
                f"{_GITHUB_API}/repos/{repo}/pulls/{pr_number}",
                headers=headers,
                json={"state": "closed"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def merge_pull_request(
    installation_id: int, repo: str, pr_number: int, sha: Optional[str] = None
) -> bool:
    """Merge a PR (used by Phase 2 auto-merge). Squash merge."""
    headers = await _headers(installation_id)
    if headers is None:
        return False
    body: dict = {"merge_method": "squash"}
    if sha:
        body["sha"] = sha
    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.put(
                f"{_GITHUB_API}/repos/{repo}/pulls/{pr_number}/merge",
                headers=headers,
                json=body,
            )
            return resp.status_code == 200
    except Exception:
        return False


async def delete_branch(installation_id: int, repo: str, branch: str) -> bool:
    """Best-effort branch cleanup after merge/dismiss (O2)."""
    headers = await _headers(installation_id)
    if headers is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.delete(
                f"{_GITHUB_API}/repos/{repo}/git/refs/heads/{branch}", headers=headers
            )
            return resp.status_code in (204, 422)
    except Exception:
        return False


def config_slug() -> str:
    from ... import config

    return config.GITHUB_APP_SLUG
