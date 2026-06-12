#!/usr/bin/env python3
"""
Inject (or restore) a bug in demo/service.py to test the Orqis loop.

  python demo/break.py            inject the bug
  python demo/break.py --restore  put the file back

The bug is a realistic one-character typo in apply_discount() —
`discount` becomes `discont` — so every order crashes with a NameError.
"""

import os
import sys

SERVICE = os.path.join(os.path.dirname(__file__), "service.py")

HEALTHY = "    return round(price * quantity * (1 - discount), 2)"
BUGGED  = "    return round(price * quantity * (1 - discont), 2)"


def main() -> None:
    restore = "--restore" in sys.argv

    with open(SERVICE, "r", encoding="utf-8") as f:
        src = f.read()

    if restore:
        if BUGGED not in src:
            print("service.py is already healthy — nothing to restore.")
            return
        src = src.replace(BUGGED, HEALTHY)
        action = "restored"
    else:
        if BUGGED in src:
            print("service.py is already bugged — run with --restore first.")
            return
        if HEALTHY not in src:
            print("error: could not find the target line in service.py")
            sys.exit(1)
        src = src.replace(HEALTHY, BUGGED)
        action = "bugged"

    with open(SERVICE, "w", encoding="utf-8") as f:
        f.write(src)

    print(f"service.py {action}. Restart the service for it to take effect:")
    print("  python demo/service.py 2>&1 | orqis monitor --source shop-api")


if __name__ == "__main__":
    main()
