"""
Universal log body normalizer.

Takes raw HTTP request bytes (any content-type, any structure) and returns
a flat list of plain-text strings — one per log line. The pattern_matcher
then classifies each string as usual.

Format detection is done by inspection, not by trusting Content-Type headers
(clients lie). Detection order is:

  1. JSON array          [ {...}, {...} ]  or  [ "line", "line" ]
  2. NDJSON              {...}\n{...}\n     (Railway, Datadog, Vercel, Fly.io)
  3. Single JSON object  {...}             (some webhook-style drains)
  4. Plain text          arbitrary lines   (Docker, syslog, everything else)

Each JSON object is flattened to a string by extracting known message fields
in priority order. If no known field exists, the whole object is serialized as
a compact JSON string — worse than ideal but never silently dropped.

The normalizer never raises. If a chunk cannot be parsed, it is returned as-is
so the error line is still visible on the dashboard.
"""

import json
from typing import Any


# Field names checked in priority order when extracting the message from a
# structured log object. Covers: Python logging, Go zerolog/zap, Node winston,
# Pino, Datadog, Railway, Fly.io, Vercel, Docker, AWS CloudWatch, GCP.
_MSG_FIELDS = [
    "message", "msg", "log", "text", "body",
    "error", "err", "exception",
]

_LEVEL_FIELDS = [
    "level", "severity", "lvl", "loglevel", "log_level", "status",
]

_TS_FIELDS = [
    "timestamp", "ts", "time", "datetime", "date", "@timestamp",
]

_SOURCE_FIELDS = [
    "service", "source", "logger", "name", "app", "container",
    "hostname", "host", "component",
]


def normalize(raw: bytes) -> list[str]:
    """
    Convert raw HTTP body bytes into a flat list of log line strings.
    Never raises.
    """
    try:
        text = raw.decode("utf-8", errors="replace").strip()
    except Exception:
        return []

    if not text:
        return []

    # --- Try JSON array first ------------------------------------------------
    if text.startswith("["):
        try:
            items = json.loads(text)
            if isinstance(items, list):
                return [_item_to_line(i) for i in items if i]
        except json.JSONDecodeError:
            pass

    # --- Try NDJSON (multiple JSON objects, one per line) --------------------
    # Must check before plain-text because NDJSON lines start with "{"
    if text.startswith("{"):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        parsed: list[str] = []
        all_json = True
        for line in lines:
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                    parsed.append(_obj_to_line(obj))
                    continue
                except json.JSONDecodeError:
                    pass
            all_json = False
            parsed.append(line)

        # If at least one line was valid JSON, treat the whole body as NDJSON
        if any(l for l in parsed):
            return parsed

    # --- Single JSON object --------------------------------------------------
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                # Could be a webhook with a nested "logs" or "lines" array
                for key in ("logs", "lines", "records", "events", "data"):
                    val = obj.get(key)
                    if isinstance(val, list):
                        return [_item_to_line(i) for i in val if i]
                return [_obj_to_line(obj)]
        except json.JSONDecodeError:
            pass

    # --- Plain text (fallback) -----------------------------------------------
    # Split on newlines, keep non-empty lines
    return [l for l in text.splitlines() if l.strip()]


# --- Object flattening helpers -----------------------------------------------

def _item_to_line(item: Any) -> str:
    """Convert one element of a JSON array to a plain-text line."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return _obj_to_line(item)
    # Numbers, booleans, etc. — shouldn't appear in logs but handle gracefully
    return str(item)


def _obj_to_line(obj: dict) -> str:
    """
    Reconstruct a human-readable log line from a structured JSON object.

    Tries to produce:  "<timestamp> <level> <source> <message>"
    Falls back to compact JSON if required fields are missing.

    Handles Fly.io's nested structure: {"event":{"message":"..."},"log":{"level":"..."}}
    by searching one level into common wrapper keys before giving up.
    """
    if not isinstance(obj, dict):
        return json.dumps(obj, ensure_ascii=False)

    # Fly.io wraps fields inside sub-objects like "event", "log", "fly"
    # Merge any dict-valued top-level keys so _pick can find nested fields.
    flat = dict(obj)
    for wrapper_key in ("event", "log", "fly", "kubernetes", "docker", "fields"):
        nested = obj.get(wrapper_key)
        if isinstance(nested, dict):
            # Don't overwrite already-present top-level keys
            for k, v in nested.items():
                if k not in flat:
                    flat[k] = v

    message = _pick(flat, _MSG_FIELDS) or ""
    level   = _pick(flat, _LEVEL_FIELDS) or ""
    ts      = _pick(flat, _TS_FIELDS) or ""
    source  = _pick(flat, _SOURCE_FIELDS) or ""

    if message:
        parts = [p for p in [ts, level.upper() if level else "", source, message] if p]
        return " ".join(parts)

    # No recognizable message field — fall back to compact JSON
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _pick(obj: dict, fields: list[str]) -> str:
    """Return the first non-empty string value found among the given field names."""
    for f in fields:
        val = obj.get(f)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
        # Some loggers nest error under {"error": {"message": "..."}}
        if isinstance(val, dict):
            nested = val.get("message") or val.get("msg") or val.get("text")
            if nested and isinstance(nested, str):
                return nested.strip()
    return ""
