"""Simulate an instrumented refund agent stuck in a runaway tool loop.

Emits repeated tool.start trace events (same tool + args + source) so Orqis's
behavioural detector trips its circuit breaker and triggers the deterministic
remediation against refund_agent.py in the local repo clone.
"""

import os
import time
import uuid
from datetime import datetime, timezone

import httpx

BACKEND = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")
REPO = r"C:\Users\siddu\.cursor\projects\empty-window\Orqis-Auto-Agent-DevOps\e2e-workspace"
LOOP_FILE = os.path.join(REPO, "refund_agent.py")
CODE_LOCATION = f"{LOOP_FILE}:21:resolve_refund"
SOURCE = "refund-agent"
RUN_ID = str(uuid.uuid4())

# A real gpt-4o-ish per-call cost so the recovered-cost figure is meaningful.
COST_PER_CALL = 0.0123


def emit(n: int) -> dict:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "tool.start",
        "provider": "langchain",
        "run_id": RUN_ID,
        "model": "gpt-4o",
        "tool_name": "check_order_status",
        "tool_args": '{"order_id": "1042"}',
        "code_location": CODE_LOCATION,
        "cost_usd": COST_PER_CALL,
        "source": SOURCE,
    }
    r = httpx.post(f"{BACKEND}/trace", json=event, timeout=15.0)
    r.raise_for_status()
    return r.json()


def main() -> int:
    print(f"Driving runaway loop -> {BACKEND}, source={SOURCE}")
    tripped_at = None
    for i in range(1, 13):
        resp = emit(i)
        broke = resp.get("circuit_break")
        print(f"  call {i:>2}: circuit_break={broke}")
        if broke and tripped_at is None:
            tripped_at = i
        time.sleep(0.2)
    if tripped_at:
        print(f"Circuit breaker tripped at call {tripped_at}.")
        return 0
    print("Detector did not trip — check threshold/window.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
