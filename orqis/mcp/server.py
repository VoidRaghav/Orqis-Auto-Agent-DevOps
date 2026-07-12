"""
Orqis MCP server — IDE-agnostic (stdio JSON-RPC 2.0).

Works with any editor or agent that supports the Model Context Protocol:
  - Cursor, Windsurf, Claude Code (project `.mcp.json` or user config)
  - VS Code / GitHub Copilot (MCP servers in settings)
  - Zed, JetBrains, and other MCP-compatible tools

Setup (same for all — spawn `orqis mcp` over stdio):
  {
    "mcpServers": {
      "orqis": {
        "command": "orqis",
        "args": ["mcp", "--backend-url", "http://localhost:8000"],
        "env": { "ORQIS_ADMIN_TOKEN": "your-token-if-set" }
      }
    }
  }

When ORQIS_ADMIN_TOKEN is set on the backend, pass it via env or --admin-token
so approve/dismiss/open-pr/resolve work from the IDE assistant.
"""

import json
import os
import sys
from typing import Any, Optional

import httpx

from . import client as mcp_http

_TOOLS = [
    {
        "name": "list_incidents",
        "description": (
            "List recent Orqis incidents (open, patching, patched, pr_open, resolved, etc.). "
            "Call first to see production errors and suggested fixes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max incidents (default 20, max 50)",
                    "default": 20,
                }
            },
        },
    },
    {
        "name": "get_incident",
        "description": (
            "Full incident details: code context, validation, diff, PR URL if opened. "
            "Use before approving or opening a PR."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "get_incident_prompt",
        "description": (
            "IDE-agnostic fix prompt to paste into any AI chat (VS Code, Cursor, Claude Code, "
            "Windsurf, JetBrains, terminal agents). Includes error, context, and diff."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "approve_incident",
        "description": (
            "Apply the patch to the local workspace (local-dev path only). "
            "For GitHub-mapped incidents, use open_pr or merge the PR on GitHub instead. "
            "Low-confidence patches need force=true after review."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "open_pr",
        "description": (
            "Open (or retry) a fix pull request on GitHub for an incident. "
            "Requires GitHub App connected and repo mapped."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "resolve_incident",
        "description": (
            "Mark an incident resolved (e.g. PR merged but webhook missed)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "dismiss_incident",
        "description": "Dismiss an incident — no local apply; closes open PR if any.",
        "inputSchema": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"],
        },
    },
    {
        "name": "watch_incidents",
        "description": (
            "Poll for new or updated incidents (open/patched/pr_open). "
            "Use for proactive IDE notifications between agent turns."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since_seconds": {
                    "type": "integer",
                    "description": "Only incidents from the last N seconds (default 60)",
                    "default": 60,
                },
                "status": {
                    "type": "string",
                    "description": "Optional status filter (e.g. patched, pr_open)",
                },
            },
        },
    },
]


def _handle_list_incidents(backend: str, admin_token: str, args: dict) -> str:
    limit = min(int(args.get("limit", 20)), 50)
    r = mcp_http.get_json(backend, "/incidents", params={"limit": limit})
    r.raise_for_status()
    incidents = r.json()
    if not incidents:
        return "No incidents found."
    lines = []
    for inc in incidents:
        status = inc.get("status", "unknown")
        err = inc.get("error_message", "")[:120]
        fp = inc.get("repo_relative_path") or inc.get("file_path") or ""
        line = inc.get("error_line") or ""
        loc = f" @ {fp}:{line}" if fp else ""
        flags = []
        if inc.get("diff"):
            flags.append("has diff")
        if inc.get("pr_url"):
            flags.append(f"pr={inc.get('pr_url')}")
        if inc.get("repo_full_name"):
            flags.append(f"repo={inc['repo_full_name']}")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        conf = inc.get("confidence")
        conf_flag = f" confidence={conf}/100" if conf is not None else ""
        lines.append(f"[{status}]{flag_str}{conf_flag} id={inc['id']}{loc}\n  {err}")
    return "\n\n".join(lines)


def _handle_get_incident(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    r = mcp_http.get_json(backend, f"/incidents/{iid}")
    if r.status_code == 404:
        return f"Incident {iid} not found."
    r.raise_for_status()
    inc = r.json()
    parts = [
        f"id: {inc['id']}",
        f"status: {inc.get('status')}",
        f"error: {inc.get('error_message', '')}",
        f"interpretation: {inc.get('interpretation', '')}",
    ]
    path = inc.get("repo_relative_path") or inc.get("file_path")
    if path:
        parts.append(f"file: {path}:{inc.get('error_line', '')}")
    if inc.get("repo_full_name"):
        parts.append(f"repo: {inc['repo_full_name']}")
    if inc.get("pr_url"):
        parts.append(f"pr: {inc['pr_url']}")
    if inc.get("function_name"):
        parts.append(f"function: {inc['function_name']}")
    if inc.get("code_context"):
        parts.append(
            f"\ncode context (line {inc.get('context_start_line', 1)}):\n"
            f"```python\n{inc['code_context']}\n```"
        )
    conf = inc.get("confidence")
    if conf is not None:
        parts.append(f"confidence: {conf}/100 ({inc.get('validation_status', 'pending')})")
    for err in inc.get("validation_errors") or []:
        parts.append(f"  ✗ {err}")
    for warn in inc.get("validation_warnings") or []:
        parts.append(f"  ⚠ {warn}")
    if inc.get("diff"):
        parts.append(f"\nsuggested diff:\n```diff\n{inc['diff']}\n```")
        if inc.get("status") == "low_confidence":
            parts.append(
                "\nNOTE: patch failed verification — review carefully. "
                "Local approve requires force=true; GitHub path: use open_pr."
            )
    elif inc.get("repo_full_name"):
        parts.append("\nno diff yet — wait for patched status or use get_incident_prompt")
    else:
        parts.append("\nno diff available yet")
    return "\n".join(parts)


def _handle_get_incident_prompt(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    r = mcp_http.get_json(backend, f"/incidents/{iid}/prompt")
    if r.status_code == 404:
        return f"Incident {iid} not found."
    r.raise_for_status()
    return r.json().get("prompt", "")


def _detail(r) -> str:
    try:
        return r.json().get("detail", r.text)
    except Exception:
        return r.text or str(r.status_code)


def _handle_approve_incident(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    force = bool(args.get("force", False))
    r = mcp_http.post_json(
        backend,
        f"/incidents/{iid}/approve",
        admin_token=admin_token,
        params={"force": str(force).lower()},
    )
    if r.status_code == 404:
        return f"Incident {iid} not found."
    if r.status_code == 409:
        return f"Cannot approve: {_detail(r)}"
    if r.status_code == 401:
        return "Unauthorized — set ORQIS_ADMIN_TOKEN in the MCP server env or --admin-token."
    if r.status_code == 422:
        return f"Patch failed: {_detail(r)}"
    r.raise_for_status()
    data = r.json()
    return (
        f"Patch applied to {data.get('file', 'file')}. "
        f"Incident approved. status=approved"
    )


def _handle_watch_incidents(backend: str, admin_token: str, args: dict) -> str:
    import time

    since = int(args.get("since_seconds", 60))
    status_filter = args.get("status") or ""
    r = mcp_http.get_json(backend, "/incidents", params={"limit": 50}, admin_token=admin_token)
    r.raise_for_status()
    incidents = r.json()
    cutoff = time.time() - since
    lines = []
    for inc in incidents:
        created = inc.get("created_at", "")
        try:
            from datetime import datetime

            ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        except Exception:
            ts = cutoff
        if ts < cutoff:
            continue
        st = inc.get("status", "")
        if status_filter and st != status_filter:
            continue
        lines.append(
            f"[{st}] id={inc['id']} pr={inc.get('pr_url') or '-'} "
            f"{inc.get('error_message', '')[:80]}"
        )
    return "\n".join(lines) if lines else "No recent incidents in window."


def _handle_open_pr(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    r = mcp_http.post_json(
        backend, f"/incidents/{iid}/open-pr", admin_token=admin_token
    )
    if r.status_code == 404:
        return f"Incident {iid} not found."
    if r.status_code == 401:
        return "Unauthorized — set ORQIS_ADMIN_TOKEN in the MCP server env."
    if r.status_code == 409:
        return f"Cannot open PR: {_detail(r)}"
    r.raise_for_status()
    detail = mcp_http.get_json(backend, f"/incidents/{iid}", admin_token=admin_token)
    if detail.status_code == 200:
        inc = detail.json()
        return (
            f"PR flow started for {iid}: status={inc.get('status')} "
            f"pr_url={inc.get('pr_url') or 'pending'} "
            f"pr_error={inc.get('pr_error') or 'none'}"
        )
    return "Opening fix PR on GitHub — poll get_incident for pr_url."


def _handle_resolve_incident(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    r = mcp_http.post_json(
        backend, f"/incidents/{iid}/resolve", admin_token=admin_token
    )
    if r.status_code == 404:
        return f"Incident {iid} not found."
    if r.status_code == 401:
        return "Unauthorized — set ORQIS_ADMIN_TOKEN in the MCP server env."
    r.raise_for_status()
    return f"Incident {iid} marked resolved."


def _handle_dismiss_incident(backend: str, admin_token: str, args: dict) -> str:
    iid = args["incident_id"]
    r = mcp_http.post_json(
        backend, f"/incidents/{iid}/dismiss", admin_token=admin_token
    )
    if r.status_code == 404:
        return f"Incident {iid} not found."
    if r.status_code == 401:
        return "Unauthorized — set ORQIS_ADMIN_TOKEN in the MCP server env."
    r.raise_for_status()
    return f"Incident {iid} dismissed."


_HANDLERS = {
    "list_incidents": _handle_list_incidents,
    "get_incident": _handle_get_incident,
    "get_incident_prompt": _handle_get_incident_prompt,
    "approve_incident": _handle_approve_incident,
    "open_pr": _handle_open_pr,
    "resolve_incident": _handle_resolve_incident,
    "dismiss_incident": _handle_dismiss_incident,
    "watch_incidents": _handle_watch_incidents,
}


def _send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _ok(req_id: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Optional[Any], code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _handle_request(req: dict, backend: str, admin_token: str) -> None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "orqis", "version": "0.2.0"},
        })

    elif method == "initialized":
        pass

    elif method == "tools/list":
        _ok(req_id, {"tools": _TOOLS})

    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name", "")
        call_args = params.get("arguments", {})
        handler = _HANDLERS.get(name)
        if handler is None:
            _err(req_id, -32601, f"unknown tool: {name}")
            return
        try:
            text = handler(backend, admin_token, call_args)
            _ok(req_id, {"content": [{"type": "text", "text": text}]})
        except httpx.ConnectError:
            _err(req_id, -32603, f"Orqis backend unreachable at {backend}")
        except Exception as e:
            _err(req_id, -32603, str(e))

    elif method == "ping":
        _ok(req_id, {})

    else:
        if req_id is not None:
            _err(req_id, -32601, f"method not found: {method}")


def run(
    backend_url: str = "http://localhost:8000",
    admin_token: str = "",
) -> None:
    """
    MCP stdio loop — spawned by any IDE/agent that supports MCP.
    """
    token = admin_token or os.getenv("ORQIS_ADMIN_TOKEN", "")
    print(
        f"[orqis-mcp] server started, backend={backend_url}, "
        f"admin={'yes' if token else 'no'}",
        file=sys.stderr,
    )
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as e:
            _err(None, -32700, f"parse error: {e}")
            continue
        _handle_request(req, backend_url, token)
