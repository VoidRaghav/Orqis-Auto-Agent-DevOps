"""
Signed state tokens for the GitHub App post-install callback (C1).

The install URL includes a short-lived HMAC-signed `state` query param. The
callback rejects requests without a valid state so arbitrary callers cannot
point Orqis at a foreign installation_id.
"""

import base64
import hashlib
import hmac
import secrets
import time

_STATE_TTL_SECONDS = 3600


def _signing_key() -> bytes:
    from ... import config

    key = (
        config.ADMIN_TOKEN
        or config.RELOAD_SECRET
        or config.GITHUB_WEBHOOK_SECRET
        or "orqis-dev-install-state"
    )
    return key.encode()


def create_state() -> str:
    """Return a URL-safe signed state token for the GitHub install URL."""
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    payload = f"{ts}.{nonce}"
    sig = hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}.{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_state(state: str) -> bool:
    """Return True when `state` is authentic and within the TTL window."""
    if not state:
        return False
    try:
        padded = state + "=" * (-len(state) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        payload, sig = decoded.rsplit(".", 1)
        expected = hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        ts_str = payload.split(".", 1)[0]
        if int(time.time()) - int(ts_str) > _STATE_TTL_SECONDS:
            return False
        return True
    except Exception:
        return False
