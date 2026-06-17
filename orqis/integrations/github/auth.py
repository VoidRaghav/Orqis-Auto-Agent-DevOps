"""
GitHub App authentication.

Two token layers:
  1. App JWT  — short-lived (10 min), signed with the app's RSA private key.
                Identifies Orqis as the app itself. Used only to mint (2).
  2. Installation token — scoped to the repos a user granted, valid 1 hour.
                Used for all repo operations (read file, commit, open PR).

Installation tokens are cached in-process keyed by installation_id and refreshed
a minute before expiry. Never raises on a missing key — callers get None and
degrade to interpretation-only.
"""

import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from ... import config

_GITHUB_API = "https://api.github.com"

# installation_id -> (token, expires_at_unix)
_token_cache: dict[int, tuple[str, float]] = {}


def _load_private_key() -> Optional[str]:
    """Return the PEM private key from env (inline value or file path)."""
    if config.GITHUB_APP_PRIVATE_KEY.strip():
        return config.GITHUB_APP_PRIVATE_KEY
    if config.GITHUB_APP_PRIVATE_KEY_PATH:
        try:
            with open(config.GITHUB_APP_PRIVATE_KEY_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    return None


def is_configured() -> bool:
    """True when the GitHub App credentials are present."""
    return bool(config.GITHUB_APP_ID and _load_private_key())


def _app_jwt() -> Optional[str]:
    """
    Build a signed JWT identifying the app. iat is backdated 60s to tolerate
    clock skew between Orqis and GitHub (GitHub rejects future iat).
    """
    key = _load_private_key()
    if not key or not config.GITHUB_APP_ID:
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        return None

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,  # 10 min — GitHub's max
        "iss": config.GITHUB_APP_ID,
    }
    try:
        return jwt.encode(payload, key, algorithm="RS256")
    except Exception:
        return None


async def installation_token(installation_id: int) -> Optional[str]:
    """
    Return a valid installation access token, minting/refreshing as needed.
    Cached until ~1 min before expiry. Returns None if the app isn't
    configured or GitHub rejects the request.
    """
    cached = _token_cache.get(installation_id)
    if cached and cached[1] - 60 > time.time():
        return cached[0]

    jwt_token = _app_jwt()
    if jwt_token is None:
        return None

    url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    token = data.get("token")
    expires_at = data.get("expires_at")
    if not token:
        return None

    try:
        exp_unix = datetime.fromisoformat(
            expires_at.replace("Z", "+00:00")
        ).timestamp()
    except (AttributeError, ValueError):
        exp_unix = time.time() + 3600

    _token_cache[installation_id] = (token, exp_unix)
    return token


async def list_installation_repos(installation_id: int) -> list[str]:
    """
    Return the full names ("owner/repo") of every repo the installation can
    access. Used to populate the Settings repo picker and to guard operations.
    """
    token = await installation_token(installation_id)
    if token is None:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[str] = []
    page = 1
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            while True:
                resp = await http.get(
                    f"{_GITHUB_API}/installation/repositories",
                    headers=headers,
                    params={"per_page": 100, "page": page},
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("repositories", [])
                repos.extend(r["full_name"] for r in batch if r.get("full_name"))
                if len(batch) < 100:
                    break
                page += 1
    except Exception:
        return repos
    return repos


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
