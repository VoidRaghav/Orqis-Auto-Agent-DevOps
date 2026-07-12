"""Sync GitHub App installation repos into workspace settings."""

from __future__ import annotations

from ...backend import store
from . import auth, client


async def refresh_installation_repos(installation_id: int) -> dict:
    repos = await auth.list_installation_repos(installation_id)
    account_login = await auth.installation_account_login(installation_id)
    repo_branches: dict[str, str] = {}
    for repo in repos:
        default = await client.get_default_branch(installation_id, repo)
        if default:
            repo_branches[repo] = default[0]
    return await store.save_settings(
        {
            "installation_id": installation_id,
            "repos": repos,
            "account_login": account_login,
            "repo_default_branches": repo_branches,
        }
    )
