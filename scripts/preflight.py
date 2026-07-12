#!/usr/bin/env python3
"""Hard-abort if dogfood prerequisites are not met (R5).

Run before harness tests:
    python scripts/preflight.py
"""

import os
import shutil
import sys
from pathlib import Path

import httpx
import redis

BACKEND = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
PROJECT_ROOT = os.getenv("ORQIS_PROJECT_ROOT", "")


def _fail(msg: str) -> None:
    print(f"preflight FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not os.getenv("ORQIS_ADMIN_TOKEN", "").strip():
        _fail("ORQIS_ADMIN_TOKEN is not set (required for dogfood)")

    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
    except Exception as e:
        _fail(f"Redis unreachable at {REDIS_URL}: {e}")

    try:
        resp = httpx.get(f"{BACKEND.rstrip('/')}/health", timeout=10.0)
        if resp.status_code != 200:
            _fail(f"backend unhealthy: GET /health returned {resp.status_code}")
        data = resp.json()
        if data.get("status") != "ok":
            _fail(f"backend unhealthy: status={data.get('status')!r}")
        probe = httpx.get(f"{BACKEND.rstrip('/')}/incidents?limit=1", timeout=10.0)
        if probe.status_code != 200:
            _fail(
                f"not Orqis backend: GET /incidents returned {probe.status_code} "
                f"(another app may be bound to {BACKEND})"
            )
    except Exception as e:
        _fail(f"backend unreachable at {BACKEND}: {e}")

    if not shutil.which("orqis"):
        try:
            import orqis.cli  # noqa: F401
        except ImportError:
            _fail("orqis CLI not found on PATH and orqis package not importable (pip install -e .)")

    if not PROJECT_ROOT.strip():
        _fail("ORQIS_PROJECT_ROOT is not set")

    refund_agent = Path(PROJECT_ROOT) / "src" / "refund_agent.py"
    if not refund_agent.is_file():
        _fail(
            f"missing {refund_agent} — clone orqis-test-agent and set ORQIS_PROJECT_ROOT"
        )

    print("preflight OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
