"""
Normalize third-party observability payloads into Orqis log lines.

Each adapter returns (lines, source) for the existing drain/ingest pipeline.
"""

from __future__ import annotations

import json
from typing import Any


def from_datadog(body: dict) -> tuple[list[str], str]:
    source = body.get("source") or body.get("service") or "datadog"
    lines: list[str] = []
    for entry in body.get("events") or body.get("logs") or [body]:
        if isinstance(entry, str):
            lines.append(entry)
        elif isinstance(entry, dict):
            msg = entry.get("message") or entry.get("msg") or json.dumps(entry)
            lines.append(str(msg))
    return lines or [json.dumps(body)], f"datadog:{source}"


def from_cloudwatch(body: dict) -> tuple[list[str], str]:
    source = body.get("logGroup") or body.get("logStream") or "cloudwatch"
    lines: list[str] = []
    for ev in body.get("logEvents") or []:
        lines.append(ev.get("message", ""))
    if body.get("message"):
        lines.append(str(body["message"]))
    return lines or [json.dumps(body)], f"cloudwatch:{source}"


def from_otel(body: dict) -> tuple[list[str], str]:
    source = body.get("resource", {}).get("service.name") or "otel"
    lines: list[str] = []
    for item in body.get("resourceLogs") or body.get("logs") or [body]:
        if isinstance(item, dict):
            for rl in item.get("scopeLogs") or item.get("logRecords") or [item]:
                if isinstance(rl, dict):
                    msg = rl.get("body") or rl.get("message") or json.dumps(rl)
                    lines.append(str(msg))
        else:
            lines.append(str(item))
    return lines or [json.dumps(body)], f"otel:{source}"


def parse_adapter(kind: str, body: Any) -> tuple[list[str], str]:
    if not isinstance(body, dict):
        body = {"message": str(body)}
    kind = kind.lower()
    if kind == "datadog":
        return from_datadog(body)
    if kind == "cloudwatch":
        return from_cloudwatch(body)
    if kind in ("otel", "opentelemetry"):
        return from_otel(body)
    raise ValueError(f"unknown ingest adapter: {kind}")
