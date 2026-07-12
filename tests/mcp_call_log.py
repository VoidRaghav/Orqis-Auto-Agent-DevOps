#!/usr/bin/env python3
"""Stdio MCP proxy that logs tools/call requests from the Cursor SDK agent.

Spawned as the MCP server command in Tier B tests. Forwards JSON-RPC lines to
`orqis mcp` and appends {tool, args, ts} records to ORQIS_MCP_CALL_LOG (JSONL).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


def _append_log(entry: dict[str, Any]) -> None:
    path = os.environ.get("ORQIS_MCP_CALL_LOG", "").strip()
    if not path:
        return
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _maybe_log_request(line: str) -> None:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return
    if msg.get("method") != "tools/call":
        return
    params = msg.get("params") or {}
    _append_log(
        {
            "tool": params.get("name", ""),
            "args": params.get("arguments") or {},
            "ts": time.time(),
        }
    )


def _forward_stdin(proc: subprocess.Popen[str]) -> None:
    assert proc.stdin is not None
    for line in sys.stdin:
        _maybe_log_request(line)
        proc.stdin.write(line)
        proc.stdin.flush()
    proc.stdin.close()


def _forward_stdout(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()


def main() -> int:
    backend = os.environ.get("ORQIS_BACKEND_URL", "http://localhost:8000")
    cmd = ["orqis", "mcp", "--backend-url", backend]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        env=os.environ.copy(),
        text=True,
        bufsize=1,
    )
    threads = [
        threading.Thread(target=_forward_stdin, args=(proc,), daemon=True),
        threading.Thread(target=_forward_stdout, args=(proc,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    proc.wait()
    for thread in threads:
        thread.join(timeout=1.0)
    return proc.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())
