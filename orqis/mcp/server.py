"""
Orqis MCP server.

Implements the Model Context Protocol (JSON-RPC 2.0 over stdio) so that
Claude Code, Cursor, and any MCP-compatible AI coding assistant can:
  - See active incidents in real time
  - Read the generated diff for any incident
  - Approve or dismiss incidents

Setup for Claude Code (~/.claude/mcp.json or project .mcp.json):
  {
    "mcpServers": {
      "orqis": {
        "command": "orqis",
        "args": ["mcp", "--backend-url", "http://localhost:8000"]
      }
    }
  }

Once configured, Claude Code will automatically have access to the tools
below. When Orqis detects a production error and generates a patch,
Claude Code can see it, review it, and apply it — without any manual step.
"""

import json
import sys
from typing import Any, Optional

import httpx


# ---------------------------------------------------------------------------
# Tool definitions (what the AI assistant sees)
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "name": "list_incidents",
        "description": (
            "Return the most recent Orqis incidents. "
            "Each incident has an id, status (open/patched/approved/dismissed), "
            "error message, file path, and optionally a suggested fix diff. "
            "Call this first to see what production errors Orqis has detected."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max incidents to return (default 20, max 50)",
                    "default": 20,
                }
            },
        },
    },
    {
        "name": "get_incident",
        "description": (
            "Get full details of a single incident including code context and the "
            "unified diff patch Orqis generated. Use this after list_incidents to "
            "inspect a specific incident before approving."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The incident id from list_incidents",
                }
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "get_incident_prompt",
        "description": (
            "Return a ready-to-paste natural language prompt describing the incident "
            "and the suggested fix. Useful for passing to another AI tool or for "
            "copying into a chat."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "approve_incident",
        "description": (
            "Apply the Orqis-generated patch to disk and mark the incident as approved. "
            "Works directly when status is 'patched'. For 'low_confidence' incidents "
            "(patch failed verification) you must pass force=true after reviewing the "
            "diff and validation errors via get_incident. Always review first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "force": {
                    "type": "boolean",
                    "description": "Override the low-confidence block (default false)",
                    "default": False,
                },
            },
            "required": ["incident_id"],
        },
    },
    {
        "name": "dismiss_incident",
        "description": "Mark an incident as dismissed — no patch will be applied.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"}
            },
            "required": ["incident_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _handle_list_incidents(backend: str, args: dict) -> str:
    limit = min(int(args.get("limit", 20)), 50)
    r = httpx.get(f"{backend}/incidents", params={"limit": limit}, timeout=10.0)
    r.raise_for_status()
    incidents = r.json()
    if not incidents:
        return "No incidents found."
    lines = []
    for inc in incidents:
        status = inc.get("status", "unknown")
        err = inc.get("error_message", "")[:120]
        fp = inc.get("file_path") or ""
        line = inc.get("error_line") or ""
        loc = f" @ {fp}:{line}" if fp else ""
        diff_flag = " [has diff]" if inc.get("diff") else ""
        conf = inc.get("confidence")
        conf_flag = f" confidence={conf}/100" if conf is not None else ""
        lines.append(f"[{status}]{diff_flag}{conf_flag} id={inc['id']}{loc}\n  {err}")
    return "\n\n".join(lines)


def _handle_get_incident(backend: str, args: dict) -> str:
    iid = args["incident_id"]
    r = httpx.get(f"{backend}/incidents/{iid}", timeout=10.0)
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
    if inc.get("file_path"):
        parts.append(f"file: {inc['file_path']}:{inc.get('error_line', '')}")
    if inc.get("function_name"):
        parts.append(f"function: {inc['function_name']}")
    if inc.get("code_context"):
        parts.append(f"\ncode context (line {inc.get('context_start_line', 1)}):\n```python\n{inc['code_context']}\n```")
    # Verification results — so the assistant can judge before approving
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
                "\nNOTE: this patch failed verification — review carefully. "
                "Approving requires ?force=true."
            )
    else:
        parts.append("\nno diff available yet")
    return "\n".join(parts)


def _handle_get_incident_prompt(backend: str, args: dict) -> str:
    iid = args["incident_id"]
    r = httpx.get(f"{backend}/incidents/{iid}/prompt", timeout=10.0)
    if r.status_code == 404:
        return f"Incident {iid} not found."
    r.raise_for_status()
    return r.json().get("prompt", "")


def _handle_approve_incident(backend: str, args: dict) -> str:
    iid = args["incident_id"]
    force = bool(args.get("force", False))
    r = httpx.post(
        f"{backend}/incidents/{iid}/approve",
        params={"force": str(force).lower()},
        timeout=15.0,
    )
    if r.status_code == 404:
        return f"Incident {iid} not found."
    if r.status_code == 409:
        return f"Cannot approve: {r.json().get('detail', 'conflict')}"
    if r.status_code == 422:
        return f"Patch failed: {r.json().get('detail', 'unknown error')}"
    r.raise_for_status()
    data = r.json()
    return f"Patch applied to {data.get('file', 'file')}. Incident approved."


def _handle_dismiss_incident(backend: str, args: dict) -> str:
    iid = args["incident_id"]
    r = httpx.post(f"{backend}/incidents/{iid}/dismiss", timeout=10.0)
    if r.status_code == 404:
        return f"Incident {iid} not found."
    r.raise_for_status()
    return f"Incident {iid} dismissed."


_HANDLERS = {
    "list_incidents": _handle_list_incidents,
    "get_incident": _handle_get_incident,
    "get_incident_prompt": _handle_get_incident_prompt,
    "approve_incident": _handle_approve_incident,
    "dismiss_incident": _handle_dismiss_incident,
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 over stdio
# ---------------------------------------------------------------------------

def _send(obj: dict) -> None:
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _ok(req_id: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Optional[Any], code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _handle_request(req: dict, backend: str) -> None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        _ok(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "orqis", "version": "0.1.0"},
        })

    elif method == "initialized":
        # Notification — no response needed
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
            text = handler(backend, call_args)
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


def run(backend_url: str = "http://localhost:8000") -> None:
    """
    Start the MCP server — reads JSON-RPC requests from stdin, writes to stdout.
    This is the process that Claude Code / Cursor spawns.
    """
    print(f"[orqis-mcp] server started, backend={backend_url}", file=sys.stderr)
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError as e:
            _err(None, -32700, f"parse error: {e}")
            continue
        _handle_request(req, backend_url)
