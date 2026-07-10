#!/usr/bin/env python3
"""
Orqis demo — a customer-support refund agent with a real, scary bug.

RefundBot works a support queue. Most tickets have a definite order status, so
resolve_refund() answers on the first check and the customer is helped — the
agent looks perfectly healthy. Ticket #1042 is the trap: its status is
truthfully "processing", which the while loop has no exit condition for, so it
calls the tool forever. Nothing crashes; no traceback; no linter or unit test
catches it. Orqis catches it from the live trace stream and trips a circuit
breaker, then files an incident with a verified fix.

Two ways to run it:

  Local apply (fix patches this file, agent re-runs healthy on your machine):
      python demo/support_agent.py

  Hosted GitHub PR flow (fix arrives as a real PR on the connected repo):
      ORQIS_BACKEND_URL=https://<your-backend> \
      ORQIS_DEMO_CODE_LOCATION=refund_agent.py:21:resolve_refund \
      python demo/support_agent.py
"""

import json
import os
import random
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

BACKEND_URL = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")
SOURCE = "support-agent"
ORDER_ID = "1042"

# The morning's support queue. The first two orders have a definite status, so
# the loop in resolve_refund exits on the first check and the customer gets an
# answer — the agent looks perfectly healthy. Ticket #1042 is the trap: its
# status is truthfully "processing", which the loop has no exit condition for.
ORDER_STATUS = {"1007": "shipped", "1023": "delivered", ORDER_ID: "processing"}
TICKETS = ["1007", "1023", ORDER_ID]

# Use Orqis's real production pricing engine to cost each call. Falls back to
# the same gpt-4o formula if the package isn't importable, so cost is always
# derived from tokens × price — never a made-up number.
try:
    from orqis.instrumentation import costs as _costs

    def _cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
        return _costs.calculate(model, input_tokens, output_tokens) or 0.0
except Exception:
    def _cost_for(model: str, input_tokens: int, output_tokens: int) -> float:
        return round((input_tokens * 2.50 + output_tokens * 10.00) / 1_000_000, 8)

# Demo backstop only. The bug is a genuinely unbounded loop — this cap exists
# so the session can never run forever if the backend is down. Orqis trips the
# real circuit breaker long before this (around call 8).
MAX_CALLS = 60


# ─────────────────────────── business logic ───────────────────────────
# This is the code under test. resolve_refund is what a founder would write,
# and it is exactly where the bug is: the while loop has no exit condition, so
# if the status never moves past "processing" it calls the tool forever.

def resolve_refund(order_id: str) -> str:
    """Answer the customer's refund question by checking the order status."""
    status = check_order_status(order_id)
    while status == "processing":
        status = check_order_status(order_id)
    return f"Your refund for order {order_id} is {status}."


# Line that falls inside resolve_refund so Orqis can locate the loop without a
# traceback. Robust to the function moving within the file.
_LOOP_LINE = resolve_refund.__code__.co_firstlineno + 3

# Where Orqis should locate the loop. Defaults to this local file (local-apply
# demo). For the hosted GitHub PR flow, set ORQIS_DEMO_CODE_LOCATION to the
# repo file, e.g. "refund_agent.py:21:resolve_refund", so the source resolver
# maps it to the connected repo and opens a real PR there.
CODE_LOCATION = os.getenv(
    "ORQIS_DEMO_CODE_LOCATION",
    f"{os.path.abspath(__file__)}:{_LOOP_LINE}:resolve_refund",
)


# ─────────────────────── instrumentation layer ────────────────────────
# In a real deployment this is the agent SDK / tool wrapper. It does the
# accounting, streams each call to Orqis, and enforces the circuit breaker.
# It is NOT business logic — which is the point: the fix belongs in
# resolve_refund, not here.

class CircuitBreak(Exception):
    """Raised by the wrapper when Orqis trips the breaker (or the backstop hits)."""
    def __init__(self, calls: int, spent: float, backstop: bool = False):
        self.calls = calls
        self.spent = spent
        self.backstop = backstop


# Per-session counters and the live event sink. run_session() resets these.
_calls = 0
_spent = 0.0
_checks: dict = {}
_sink: Optional[Callable[[dict], None]] = None


def check_order_status(order_id: str) -> str:
    """
    The order-status tool. It works perfectly — order 1042 really is still
    processing. That truthful-but-ambiguous answer is what the agent has no
    exit condition for. The wrapper streams the call to Orqis and enforces the
    circuit breaker Orqis trips.
    """
    global _calls, _spent
    _calls += 1
    _checks[order_id] = _checks.get(order_id, 0) + 1
    status = ORDER_STATUS.get(order_id, "processing")

    # A real agent turn: a large, growing context (system prompt + tool schemas
    # + conversation history) and a short tool-decision output. Cost is computed
    # exactly the way the production SDK does it — real per-1M-token gpt-4o
    # pricing via orqis.instrumentation.costs — not a made-up number.
    input_tokens = 18000 + _calls * 800
    output_tokens = random.randint(150, 260)
    cost = _cost_for("gpt-4o", input_tokens, output_tokens)
    _spent += cost
    _emit({
        "type": "call",
        "n": _calls,
        "check": _checks[order_id],
        "tool": "check_order_status",
        "args": order_id,
        "result": status,
        "cost": round(cost, 4),
        "spent": round(_spent, 2),
    })

    if _send_trace(order_id, input_tokens, output_tokens, cost):
        raise CircuitBreak(_calls, _spent)
    if _calls >= MAX_CALLS:
        raise CircuitBreak(_calls, _spent, backstop=True)

    time.sleep(0.45)
    return status


def _send_trace(order_id: str, input_tokens: int, output_tokens: int, cost: float) -> bool:
    """Stream one tool call to Orqis. Returns True when the breaker has tripped."""
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "tool.start",
        "provider": "openai",
        "run_id": f"refund-{order_id}",
        "model": "gpt-4o",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "latency_ms": random.randint(280, 620),
        "tool_name": "check_order_status",
        "tool_args": order_id,
        "code_location": CODE_LOCATION,
        "source": SOURCE,
    }
    data = json.dumps(event).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/trace",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read() or b"{}")
            return bool(body.get("circuit_break"))
    except Exception as e:
        _emit({"type": "warn", "text": f"could not reach Orqis ({type(e).__name__}) — relying on backstop"})
        return False


def reset_backend() -> bool:
    """Clear Orqis's anomaly + dedup state so a session re-trips cleanly."""
    req = urllib.request.Request(f"{BACKEND_URL}/demo/reset", data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10):
            return True
    except Exception:
        return False


def run_session(emit: Optional[Callable[[dict], None]] = None) -> dict:
    """
    Work the morning's ticket queue start to finish, streaming structured events
    to `emit` (the terminal CLI and the web UI both subscribe). The first two
    tickets resolve normally — proof the agent works — then ticket #1042 hits
    the unbounded loop. Resets per-session state so it can be called repeatedly.
    """
    global _calls, _spent, _checks, _sink
    _calls, _spent, _checks = 0, 0.0, {}
    _sink = emit
    reset_backend()

    _emit({"type": "online", "backend": BACKEND_URL})
    helped = 0
    result: dict = {}

    for order_id in TICKETS:
        _emit({"type": "customer", "order": order_id,
               "text": f"Where is my refund for order #{order_id}?"})
        try:
            outcome = resolve_refund(order_id)
        except CircuitBreak as cb:
            kind = "backstop" if cb.backstop else "halted"
            result = {"type": kind, "order": order_id,
                      "calls": _checks.get(order_id, cb.calls),
                      "spent": round(cb.spent, 2), "helped": helped}
            break
        helped += 1
        checks = _checks.get(order_id, 0)
        if order_id == ORDER_ID:
            # The once-stuck ticket completed — the applied fix is live.
            result = {"type": "resolved", "order": order_id, "text": outcome,
                      "calls": checks, "spent": round(_spent, 2), "helped": helped}
        else:
            _emit({"type": "ticket_done", "order": order_id, "text": outcome,
                   "checks": checks, "helped": helped})
            time.sleep(0.9)

    _emit(result)
    _sink = None
    return result


def _emit(event: dict) -> None:
    """
    Fan one structured event out to: the live UI sink (web), stdout (terminal),
    and Orqis's log stream so the dashboard ACTIVITY tab shows the agent working
    in real time — both while it is broken and after it is fixed.
    """
    if _sink is not None:
        try:
            _sink(event)
        except Exception:
            pass

    line = _plain_line(event)
    if line is None:
        return
    level = _level_for(event)
    print(f"{datetime.now().strftime('%H:%M:%S')} support-agent {level} {line}", flush=True)
    _send_log(line, level)


def _plain_line(event: dict) -> Optional[str]:
    """
    Raw operational log line for stdout and the Orqis ACTIVITY stream — the kind
    of feed a real app prints. Deliberately app-level narrative (no token/cost
    breakdown; that lives in the AI CALLS trace stream).
    """
    t = event["type"]
    if t == "online":
        return "RefundBot worker online, polling support queue"
    if t == "customer":
        return f"ticket #{event['order']} opened: customer asking about their refund"
    if t == "call":
        order = event["args"]
        if event["result"] != "processing":
            return f"ticket #{order}: order {event['result']} — refund approved"
        if event["check"] < 4:
            return f"ticket #{order}: order status is 'processing', re-checking"
        return f"ticket #{order}: order still 'processing' after {event['check']} checks, no progress"
    if t == "ticket_done":
        return f"ticket #{event['order']} resolved in {event['checks']} check(s), customer notified"
    if t == "warn":
        return event["text"]
    if t == "halted":
        return (f"RefundBot stopped on ticket #{event['order']} by Orqis after "
                f"{event['calls']} repeated checks with no progress")
    if t == "backstop":
        return f"demo backstop reached at {event['calls']} checks"
    if t == "resolved":
        return f"ticket #{event['order']} escalated to a human agent after {event['calls']} checks"
    return None


def _level_for(event: dict) -> str:
    """
    Log level for the ACTIVITY stream. Stays INFO/WARNING — nothing here ever
    errors, yet Orqis still catches the loop from the trace stream. That flat
    error rate next to a filed incident is the whole point: no exception, no
    crash, no linter would catch this.
    """
    t = event["type"]
    if t in ("halted", "backstop", "warn"):
        return "WARNING"
    if t == "call" and event["result"] == "processing" and event["check"] >= 4:
        return "WARNING"
    return "INFO"


def _send_log(line: str, level: str) -> None:
    """
    Push one log line to Orqis's ACTIVITY stream with an explicit level. Posts a
    fully-formed event (is_error stays False) so the level badge is exact and no
    RCA is triggered from the raw feed.
    """
    payload = json.dumps({
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_line": line,
        "level": level,
        "is_error": False,
        "source": SOURCE,
    }).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/events",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        run_session()
    except KeyboardInterrupt:
        sys.exit(0)
