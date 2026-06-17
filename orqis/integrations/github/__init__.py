"""
GitHub App integration for Orqis.

Orqis opens reviewable fix PRs through a GitHub App the user installs on their
repos. The app never writes to the default branch directly — every fix lands on
an `orqis/fix-*` branch and is surfaced as a PR the human merges.

Modules:
  auth.py       — App JWT + cached installation access tokens
  client.py     — thin async GitHub REST wrapper (Contents, Git Data, Pulls)
  apply_diff.py — apply a unified diff to in-memory source (no local files)
  pr_service.py — open/close/merge fix PRs with branch safety guards
  webhooks.py   — verify deliveries; handle installation + pull_request events
"""

from . import apply_diff, auth, client, pr_service, webhooks

__all__ = ["apply_diff", "auth", "client", "pr_service", "webhooks"]
