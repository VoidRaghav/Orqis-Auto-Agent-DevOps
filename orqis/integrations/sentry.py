"""
Sentry webhook integration.

Sentry sends a JSON payload for each error issue. Its exception data already
carries structured stack frames (filename, line, function, source context),
so instead of parsing raw text we reconstruct a standard Python traceback
string and feed it through the existing RCA pipeline unchanged.

Payload shape (issue/error webhook):
  {
    "data": {
      "event": {
        "exception": {
          "values": [
            {
              "type": "NameError",
              "value": "name 'discont' is not defined",
              "stacktrace": {
                "frames": [
                  {"filename": "...", "abs_path": "/abs/...", "lineno": 45,
                   "function": "apply_discount", "context_line": "    return ..."},
                  ...
                ]
              }
            }
          ]
        }
      }
    }
  }

Sentry orders frames outermost-first, so the last frame is where the error
was raised — the same order a Python traceback prints.
"""

import hashlib
import hmac
from typing import Optional


def verify_signature(body: bytes, signature: Optional[str], secret: str) -> bool:
    """
    Verify Sentry's HMAC-SHA256 webhook signature.

    Returns True when no secret is configured (local dev) or the signature
    matches. Uses a constant-time compare to avoid timing leaks.
    """
    if not secret:
        return True
    if not signature:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def extract_traceback(payload: dict) -> Optional[tuple[str, str]]:
    """
    Build a (traceback_text, source) pair from a Sentry webhook payload.

    Returns None if the payload carries no usable exception/stacktrace.
    """
    event = _dig(payload, "data", "event") or payload.get("event") or payload
    if not isinstance(event, dict):
        return None

    values = _dig(event, "exception", "values")
    if not isinstance(values, list) or not values:
        return None

    # Sentry chains exceptions outermost-first; the last value is the raised one
    exc = values[-1]
    exc_type = (exc.get("type") or "Error").strip()
    exc_value = (exc.get("value") or "").strip()

    frames = _dig(exc, "stacktrace", "frames")
    if not isinstance(frames, list):
        frames = []

    lines = ["Traceback (most recent call last):"]
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        path = frame.get("abs_path") or frame.get("filename")
        lineno = frame.get("lineno")
        func = frame.get("function") or "<module>"
        if not path or lineno is None:
            continue
        lines.append(f'  File "{path}", line {lineno}, in {func}')
        context_line = frame.get("context_line")
        if isinstance(context_line, str) and context_line.strip():
            lines.append(f"    {context_line.strip()}")

    # Terminal exception line — pattern_matcher / file_reader keys off this
    terminal = f"{exc_type}: {exc_value}" if exc_value else exc_type
    lines.append(terminal)

    # A traceback with no resolvable frames isn't actionable
    if len(lines) <= 2:
        return None

    source = _event_source(event, payload)
    return "\n".join(lines), source


def _event_source(event: dict, payload: dict) -> str:
    """Best-effort human label for the dashboard: project or server name."""
    for candidate in (
        _dig(payload, "data", "project_slug"),
        payload.get("project"),
        event.get("project"),
        _dig(event, "tags_dict", "server_name"),
        event.get("server_name"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return f"sentry:{candidate.strip()}"
    return "sentry"


def _dig(obj: object, *keys: str) -> object:
    """Safely walk nested dict keys; return None on any miss."""
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur
