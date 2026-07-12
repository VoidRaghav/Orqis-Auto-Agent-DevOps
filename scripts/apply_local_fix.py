#!/usr/bin/env python3
"""Apply Orqis fix locally to e2e-workspace for demo consistency."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "e2e-workspace" / "refund_agent.py"

FIXED = '''"""Customer-support refund agent — after Orqis auto-fix."""

import time


def check_order_status(order_id: str) -> str:
    time.sleep(0.05)
    return "processing"


def resolve_refund(order_id: str) -> str:
    status = check_order_status(order_id)
    _attempts = 0
    while status == "processing":
        if _attempts >= 5:
            return "escalated to a human agent"
        status = check_order_status(order_id)
        _attempts += 1
    return f"Your refund for order {order_id} is {status}."


if __name__ == "__main__":
    print(resolve_refund("1042"))
'''


def main() -> int:
    TARGET.write_text(FIXED, encoding="utf-8")
    print("wrote fixed", TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
