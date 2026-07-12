"""
Signed state tokens for the GitHub App post-install callback (C1).

The install URL includes a short-lived HMAC-signed `state` query param embedding
the workspace_id so the callback binds the installation to the correct tenant.
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional

_STATE_TTL_SECONDS = 3600


def _signing_key() -> bytes:
    from ... import config

    key = (
        config.SESSION_SECRET
        or config.ADMIN_TOKEN
        or config.RELOAD_SECRET
        or config.GITHUB_WEBHOOK_SECRET
    )
    if not key:
        if not config.DEV_MODE:
            raise RuntimeError(
                "install state signing secret required when ORQIS_DEV_MODE=0"
            )
        key = "orqis-dev-install-state"
    return key.encode()


def create_state(workspace_id: str) -> str:
    """Return a URL-safe signed state token for the GitHub install URL."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    payload = f"{ts}.{nonce}.{workspace_id}"
    sig = hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}.{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_state(state: str) -> bool:
    """Return True when `state` is authentic and within the TTL window."""
    return parse_state(state) is not None


def parse_state(state: str) -> Optional[str]:
    """Return workspace_id when state is valid, else None."""
    if not state:
        return None
    try:
        padded = state + "=" * (-len(state) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        payload, sig = decoded.rsplit(".", 1)
        expected = hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        parts = payload.split(".")
        if len(parts) < 3:
            return None
        ts_str, _nonce, workspace_id = parts[0], parts[1], ".".join(parts[2:])
        if int(time.time()) - int(ts_str) > _STATE_TTL_SECONDS:
            return None
        return workspace_id
    except Exception:
        return None
