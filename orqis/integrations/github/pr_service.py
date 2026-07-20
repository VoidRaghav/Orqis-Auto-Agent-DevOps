"""
Fix-PR service — turns a validated incident diff into a reviewable GitHub PR.

Never writes to the default branch. Every fix lands on an `orqis/fix-*` branch
and is surfaced as a PR the human merges. All failures are recorded on the
incident (pr_error + a non-terminal status) and never crash the pipeline.

open_fix_pr ordering (P1/P3/P4):
  create PR on GitHub
    -> persist pr_open + PR->incident index + drop incident TTL  (atomic-ish)
    -> broadcast incident.pr_opened
so the merge webhook can always resolve the incident, even if it fires fast.
"""

import asyncio
import re
from typing import Optional

from ...backend import store, ws_manager
from ...backend.models import Incident, IncidentStatus
from ...backend.tenancy import get_workspace_id
from . import apply_diff, client

_BRANCH_PREFIX = "orqis/fix-"

# Files eligible for Phase 2 auto-merge — explicit config-only allowlist (S5).
# Never source code. Matched against the repo-relative path.
_CONFIG_ALLOWLIST_EXACT = {
    ".env.example",
    "railway.toml",
    "vercel.json",
    "pyproject.toml",
}
_CONFIG_ALLOWLIST_SUFFIX = (".yaml", ".yml", ".ini", ".toml", ".cfg")
# Explicitly excluded even if a suffix would otherwise match.
_CONFIG_DENYLIST_EXACT = {"package.json", "package-lock.json"}

# Secret-looking patterns redacted from PR bodies (S4).
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(secret\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(token\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(password\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)gho_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
]


def scan_for_secrets(text: str) -> list[str]:
    """Return human-readable findings for secret-like content in diffs/PR bodies."""
    if not text:
        return []
    findings: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            findings.append(f"matched pattern: {pat.pattern[:40]}")
    return findings


def _human_error(incident: Incident) -> str:
    if incident.error_type is not None:
        return incident.error_type.value.replace("_", " ").lower()
    return "error"


def _branch_safe(name: str) -> bool:
    """Refuse to ever use a protected branch as the head."""
    return name.startswith(_BRANCH_PREFIX) and name not in ("main", "master")


def sanitize(text: str) -> str:
    """Redact secret-looking substrings before posting to GitHub (S4)."""
    if not text:
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", text)
    return text


def _pr_title(incident: Incident) -> str:
    base = incident.repo_relative_path or incident.file_path or "code"
    basename = base.split("/")[-1]
    title = f"Orqis: fix {_human_error(incident)} in {basename}"
    if incident.cost_recovered_usd:
        title += f" — ${incident.cost_recovered_usd:.2f} recovered"
    return title


def _pr_body(incident: Incident) -> str:
    lines = [
        "Automated fix opened by **Orqis** after detecting a production incident.",
        "",
        f"**Error:** {sanitize(incident.error_message)}",
    ]
    if incident.interpretation:
        lines.append(f"**What happened:** {sanitize(incident.interpretation)}")
    if incident.repo_relative_path and incident.error_line:
        lines.append(f"**Location:** `{incident.repo_relative_path}:{incident.error_line}`")
    if incident.confidence is not None:
        lines.append(f"**Confidence:** {incident.confidence}/100 ({incident.fix_method or 'llm'})")
    from ...rca.diff_split import split_by_file

    changed = [p for p, _ in split_by_file(incident.diff or "")]
    if len(changed) > 1:
        lines.append("**Files changed:** " + ", ".join(f"`{p}`" for p in changed))
    if incident.validation_warnings:
        lines.append("")
        lines.append("**Warnings:** " + "; ".join(incident.validation_warnings))
    lines.append("")
    lines.append("Review the diff and merge if it looks correct. Orqis never pushes to your default branch.")
    return "\n".join(lines)


def is_auto_merge_eligible(incident: Incident, settings: dict) -> bool:
    """
    Phase 2 — auto-merge is allowed only for deterministic, config-only fixes
    with a passing validation, and only when the toggle is on (I2/S5).
    Never for LLM-generated code. Never for .github/ CI paths or traversal.
    """
    from ...rca.safe_path import is_auto_merge_path_allowed, normalize_repo_path

    if not settings.get("auto_merge_enabled"):
        return False
    if incident.fix_method != "deterministic":
        return False
    if incident.validation_status.value != "passed":
        return False
    path = normalize_repo_path(incident.repo_relative_path or "")
    if not path or not is_auto_merge_path_allowed(path):
        return False
    basename = path.split("/")[-1].lower()
    if basename in _CONFIG_DENYLIST_EXACT:
        return False
    if basename in {p.lower() for p in _CONFIG_ALLOWLIST_EXACT}:
        return True
    return any(basename.endswith(suf) for suf in _CONFIG_ALLOWLIST_SUFFIX)


async def open_fix_pr(incident: Incident) -> None:
    """
    Open a fix PR for an incident. Idempotent: no-op if a PR already exists.
    Records pr_error + status on failure; never raises.
    """
    if incident.pr_number:
        return  # already has a PR (A4)
    if not incident.diff or not incident.repo_full_name:
        return

    async def _fail(status: IncidentStatus, reason: str) -> None:
        updated = await store.update_incident(
            incident.id, status=status.value, pr_error=reason
        )
        if updated:
            await ws_manager.manager.broadcast(
                "incident.updated", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
            )
            from ...backend import changelog

            action = (
                "patch_stale" if status == IncidentStatus.PATCH_STALE else "pr_failed"
            )
            await changelog.record(
                action,
                updated,
                reason,
            )

    secret_hits = scan_for_secrets(incident.diff)
    if secret_hits:
        await _fail(
            IncidentStatus.PR_FAILED,
            "diff blocked by secret scan: " + "; ".join(secret_hits[:3]),
        )
        return

    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        return

    repo = incident.repo_full_name

    if not await client.repo_accessible(installation_id, repo):
        await _fail(IncidentStatus.PR_FAILED, "repo not accessible to the Orqis app")
        return

    # Re-fetch the file at current default-branch HEAD and apply the diff in
    # memory. If it no longer applies, prod is behind main — flag stale (A6).
    from . import branches

    base_branch_override = branches.resolve_base_branch(settings, repo)
    default = await client.get_default_branch(
        installation_id, repo, branch=base_branch_override
    )
    if default is None:
        await _fail(IncidentStatus.PR_FAILED, "could not read default branch")
        return
    base_branch, head_sha = default

    from ...rca.diff_split import split_by_file
    from ...rca.safe_path import normalize_repo_path, validate_commit_paths

    segments = split_by_file(incident.diff)
    if not segments:
        await _fail(IncidentStatus.PR_FAILED, "no parseable file paths in diff")
        return

    cleaned_segments: list[tuple[str, str]] = []
    for path, seg_diff in segments:
        cleaned = normalize_repo_path(path)
        if cleaned is None:
            await _fail(
                IncidentStatus.PR_FAILED,
                f"unsafe repo path in diff rejected: {path!r}",
            )
            return
        cleaned_segments.append((cleaned, seg_diff))
    path_err = validate_commit_paths([p for p, _ in cleaned_segments])
    if path_err:
        await _fail(IncidentStatus.PR_FAILED, path_err)
        return

    from ...rca.validator import validate

    files_to_commit: list[tuple[str, str]] = []
    for path, seg_diff in cleaned_segments:
        normalized = apply_diff.rewrite_diff_paths(seg_diff, path)
        fetched = await client.get_file(installation_id, repo, path, head_sha)
        if fetched is None:
            await _fail(
                IncidentStatus.PR_FAILED,
                f"could not fetch {path} from GitHub (too large or missing)",
            )
            return
        current_content, _sha = fetched
        try:
            patched = apply_diff.apply_to_text(current_content, normalized)
        except apply_diff.StaleDiffError as e:
            await _fail(
                IncidentStatus.PATCH_STALE,
                f"prod may be behind {base_branch} ({path}): {e}",
            )
            return
        validation = await validate(normalized, path, source_text=current_content)
        if not validation.valid:
            await _fail(
                IncidentStatus.PR_FAILED,
                f"{path} failed validation: " + "; ".join(validation.errors[:3]),
            )
            return
        files_to_commit.append((path, validation.patched_source or patched))

    primary_path = incident.repo_relative_path or files_to_commit[0][0]
    if not incident.repo_relative_path:
        await store.update_incident(incident.id, repo_relative_path=primary_path)
        incident = await store.get_incident(incident.id) or incident

    branch = f"{_BRANCH_PREFIX}{incident.id[:8]}"
    if not _branch_safe(branch):
        await _fail(IncidentStatus.PR_FAILED, "refused unsafe branch name")
        return

    created = await client.create_branch(installation_id, repo, branch, head_sha)
    if created is None:
        await _fail(IncidentStatus.PR_FAILED, "could not create branch")
        return
    branch = created

    commit_msg = _pr_title(incident)
    commit_sha = await client.commit_files(
        installation_id, repo, branch, files_to_commit, commit_msg, head_sha,
    )
    if commit_sha is None:
        await _fail(IncidentStatus.PR_FAILED, "could not commit fix")
        return

    pr = await client.open_pull_request(
        installation_id, repo, branch, base_branch,
        _pr_title(incident), _pr_body(incident),
    )
    if pr is None:
        await _fail(IncidentStatus.PR_FAILED, "could not open pull request")
        return
    pr_number, pr_url = pr

    # Persist index + status + drop TTL atomically BEFORE broadcasting (C5/P4).
    updated = await store.finalize_pr_open(
        incident.id,
        repo,
        pr_number,
        status=IncidentStatus.PR_OPEN.value,
        pr_url=pr_url,
        branch_name=branch,
        base_branch=base_branch,
        base_sha=head_sha,
        pr_error=None,
    )
    if updated:
        await ws_manager.manager.broadcast(
            "incident.pr_opened", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
        from ...backend import changelog

        await changelog.record(
            "pr_opened",
            updated,
            f"Opened fix PR #{pr_number} on {repo}",
        )
        from ...notifications import dispatcher

        asyncio.create_task(dispatcher.notify("incident.pr_opened", updated))

    # Phase 2 — auto-merge deterministic config-only fixes.
    if updated and is_auto_merge_eligible(updated, settings):
        merged = await client.merge_pull_request(installation_id, repo, pr_number, commit_sha)
        if merged:
            await mark_resolved(updated.id, repo, pr_number, commit_sha)
        else:
            err_updated = await store.update_incident(
                incident.id,
                pr_error="auto-merge was attempted but failed — review and merge manually",
            )
            if err_updated:
                await ws_manager.manager.broadcast(
                    "incident.updated", err_updated.model_dump(mode="json")
                )


async def close_pr_for_incident(incident: Incident) -> None:
    """Close the PR + delete its branch when an incident is dismissed (G4/O2)."""
    if not incident.pr_number or not incident.repo_full_name:
        return
    settings = await store.get_settings()
    installation_id = settings.get("installation_id")
    if not installation_id:
        return
    await client.close_pull_request(installation_id, incident.repo_full_name, incident.pr_number)
    if incident.branch_name:
        await client.delete_branch(installation_id, incident.repo_full_name, incident.branch_name)
    await store.clear_pr_index(incident.repo_full_name, incident.pr_number)


async def mark_resolved(
    incident_id: str, repo: str, pr_number: int, merge_sha: Optional[str] = None
) -> Optional[Incident]:
    """
    Mark an incident resolved (PR merged), clean up its branch, re-arm the TTL,
    broadcast, and fire the hot-reload callback. Idempotent.
    """
    from ...backend import store as _store  # local alias for clarity

    incident = await _store.get_incident(incident_id)
    if incident is None:
        return None
    if incident.status == IncidentStatus.RESOLVED:
        return incident  # already handled (idempotent)

    settings = await _store.get_settings()
    installation_id = settings.get("installation_id")

    updated = await _store.update_incident(
        incident_id,
        status=IncidentStatus.RESOLVED.value,
        resolved_at=auth_now(),
    )
    # Best-effort branch cleanup (O2).
    if installation_id and incident.branch_name:
        await client.delete_branch(installation_id, repo, incident.branch_name)
    await _store.clear_pr_index(repo, pr_number)
    await _store.set_incident_ttl(incident_id)  # re-arm rolling TTL (P1)

    if updated:
        await ws_manager.manager.broadcast(
            "incident.resolved", updated.model_dump(mode="json"), workspace_id=get_workspace_id()
        )
        from ...backend import changelog

        await changelog.record(
            "pr_merged",
            updated,
            f"PR #{pr_number} merged on {repo} — fix shipped",
        )
        await _fire_hot_reload(updated, merge_sha)
    return updated


def auth_now():
    from .auth import now_utc

    return now_utc()


async def _fire_hot_reload(incident: Incident, merge_sha: Optional[str]) -> None:
    """POST a signed best-effort hot-reload callback to the user's app (O1/S3)."""
    from ... import config

    settings = await store.get_settings()
    url = settings.get("hot_reload_webhook_url")
    if not url:
        return
    if not _safe_callback_url(url):
        return

    import hashlib
    import hmac
    import json

    import httpx

    payload = {
        "incident_id": incident.id,
        "repo": incident.repo_full_name,
        "pr_number": incident.pr_number,
        "file_path": incident.repo_relative_path,
        "merge_sha": merge_sha,
    }
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if config.RELOAD_SECRET:
        sig = hmac.new(config.RELOAD_SECRET.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Orqis-Signature-256"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            await http.post(url, content=body, headers=headers)
    except Exception:
        pass  # best-effort — never block resolution on the callback


def _safe_callback_url(url: str) -> bool:
    """
    HTTPS-only and not pointing at a private/loopback/link-local address.
    Resolves all A/AAAA records to defeat DNS-rebinding (O4).
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except OSError:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
    return True
