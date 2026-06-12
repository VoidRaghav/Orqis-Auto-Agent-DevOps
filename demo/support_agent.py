#!/usr/bin/env python3
"""
Orqis demo — a customer-support refund agent with a real, scary bug.

A customer asks: "Where is my refund for order #1042?" To answer, the agent
must know the order status, so it calls a check_order_status tool. The tool
returns "processing" — true, but too vague to answer. The agent has no rule
for "stop after N tries", so it just asks again. And again. The status never
changes. The loop never ends.

Nothing crashes. The business logic is correct. The tool is correct. No linter,
no unit test, no traceback catches this. LangSmith would show you the 60 wasted
calls after the money is gone. Datadog would show the server is perfectly fine.

The looping function below is deliberately clean — this is the code a founder
would actually write. All the demo plumbing (cost, the trace stream, the kill
switch) lives in the instrumentation layer, exactly where a real agent SDK puts
it. Every tool call is streamed live to Orqis with its cost. Orqis watches the
stream, spots the same tool + same args firing with no exit condition, and trips
a circuit breaker — the next trace response tells the agent to stop.

Run it as a terminal demo:   python demo/support_agent.py
Run it as a web UI:          python demo/web_agent.py   (imports run_session)
Re-run cleanly:              curl -X POST localhost:8000/demo/reset
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
    cost = round(random.uniform(0.05, 0.09), 4)
    _spent += cost
    _emit({
        "type": "call",
        "n": _calls,
        "tool": "check_order_status",
        "args": order_id,
        "result": "processing",
        "cost": round(cost, 2),
        "spent": round(_spent, 2),
    })

    if _send_trace(_calls, cost):
        raise CircuitBreak(_calls, _spent)
    if _calls >= MAX_CALLS:
        raise CircuitBreak(_calls, _spent, backstop=True)

    time.sleep(0.45)
    return "processing"


def _send_trace(call_no: int, cost: float) -> bool:
    """Stream one tool call to Orqis. Returns True when the breaker has tripped."""
    event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": "tool.start",
        "provider": "openai",
        "run_id": f"refund-{ORDER_ID}",
        "model": "gpt-4o",
        "input_tokens": 900 + call_no * 60,   # context grows every turn
        "output_tokens": 70,
        "cost_usd": cost,
        "tool_name": "check_order_status",
        "tool_args": ORDER_ID,
        "code_location": f"{os.path.abspath(__file__)}:{_LOOP_LINE}:resolve_refund",
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
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read() or b"{}")
            return bool(body.get("circuit_break"))
    except Exception as e:
        _emit({"type": "warn", "text": f"could not reach Orqis ({type(e).__name__}) — relying on backstop"})
        return False


def reset_backend() -> bool:
    """Clear Orqis's anomaly + dedup state so a session re-trips cleanly."""
    req = urllib.request.Request(f"{BACKEND_URL}/demo/reset", data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def run_session(emit: Optional[Callable[[dict], None]] = None) -> dict:
    """
    Run one refund attempt start to finish, streaming structured events to
    `emit` (the terminal CLI and the web UI both subscribe). Resets per-session
    state so it can be called repeatedly. Returns a final summary dict.
    """
    global _calls, _spent, _sink
    _calls, _spent = 0, 0.0
    _sink = emit
    reset_backend()

    _emit({"type": "online", "backend": BACKEND_URL})
    _emit({"type": "customer", "text": f"Where is my refund for order #{ORDER_ID}?"})

    try:
        outcome = resolve_refund(ORDER_ID)
        result = {"type": "resolved", "text": outcome, "calls": _calls, "spent": round(_spent, 2)}
    except CircuitBreak as cb:
        if cb.backstop:
            result = {"type": "backstop", "calls": cb.calls, "spent": round(cb.spent, 2)}
        else:
            result = {"type": "halted", "calls": cb.calls, "spent": round(cb.spent, 2)}

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
    print(f"{datetime.now().strftime('%H:%M:%S')} support-agent {line}", flush=True)
    _send_log(line)


def _plain_line(event: dict) -> Optional[str]:
    """Human-readable, ANSI-free log line for stdout and the Orqis log stream."""
    t = event["type"]
    if t == "online":
        return "refund agent online"
    if t == "customer":
        return f'customer asks: "{event["text"]}"'
    if t == "call":
        return (f"check_order_status({event['args']}) -> '{event['result']}' "
                f"| ${event['cost']:.2f} this call | ${event['spent']:.2f} burned "
                f"| 0 resolved")
    if t == "warn":
        return event["text"]
    if t == "halted":
        return (f"Orqis circuit breaker tripped — stopped after {event['calls']} "
                f"repeated calls (${event['spent']:.2f}), runaway spend halted")
    if t == "backstop":
        return f"demo backstop reached at {event['calls']} calls (${event['spent']:.2f})"
    if t == "resolved":
        return (f"handled correctly after {event['calls']} calls (${event['spent']:.2f}) "
                f"— bounded retries, {event['text']}")
    return None


def _send_log(line: str) -> None:
    """Push one log line to Orqis so it appears in the dashboard ACTIVITY tab."""
    payload = json.dumps({"lines": [line], "source": SOURCE}).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/ingest",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        run_session()
    except KeyboardInterrupt:
        sys.exit(0)
