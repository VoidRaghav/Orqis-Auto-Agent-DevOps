#!/usr/bin/env python3
"""
Orqis demo service — a tiny order-processing API on :8100.

Used to test the full Orqis loop on a live, continuously-logging app:

  python demo/service.py 2>&1 | orqis monitor --source shop-api

The service emits a steady stream of INFO logs (a heartbeat plus synthetic
order traffic it sends to itself). While healthy, Orqis sees nothing wrong.

To break it, run `python demo/break.py` — it injects a one-character typo
into apply_discount() so every order crashes with a NameError. Restart the
service and Orqis will detect the traceback, locate the bug, and generate
a verified patch. `python demo/break.py --restore` puts it back.
"""

import json
import logging
import random
import sys
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s shop-api %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("shop-api")


# ─────────────────────────── business logic ───────────────────────────
# break.py mutates the function below — keep it self-contained.

def apply_discount(price: float, quantity: int) -> float:
    """Return the line total after any bulk discount."""
    discount = 0.15 if quantity >= 10 else 0.0
    return round(price * quantity * (1 - discont), 2)


def process_order(item: str, price: float, quantity: int) -> dict:
    total = apply_discount(price, quantity)
    return {"item": item, "quantity": quantity, "total": total}


# ─────────────────────────── http layer ───────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # silence the default per-request noise

    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._reply(200, {"status": "ok"})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/order":
            self._reply(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            data = json.loads(raw or b"{}")
            result = process_order(
                data.get("item", "widget"),
                float(data.get("price", 9.99)),
                int(data.get("quantity", 1)),
            )
            log.info(f"order ok — {result['item']} x{result['quantity']} = ${result['total']}")
            self._reply(200, result)
        except Exception:
            # Emit the full traceback so the log stream carries it to Orqis
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            self._reply(500, {"error": "order processing failed"})


# ─────────────────────────── live log stream ───────────────────────────

_ITEMS = ["widget", "gadget", "sprocket", "bolt", "gear", "flange"]


def _heartbeat() -> None:
    while True:
        time.sleep(5)
        log.info(f"heartbeat — {random.randint(2, 9)} workers idle, queue empty")


def _synthetic_traffic() -> None:
    """Send orders to our own endpoint so the log stream is always live."""
    time.sleep(2)
    while True:
        time.sleep(random.uniform(2.0, 4.0))
        order = {
            "item": random.choice(_ITEMS),
            "price": round(random.uniform(5, 50), 2),
            "quantity": random.choice([1, 2, 3, 5, 8, 12]),
        }
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{PORT}/order",
                data=json.dumps(order).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3).read()
        except Exception as e:
            log.warning(f"traffic generator could not reach endpoint: {type(e).__name__}")


def main() -> None:
    log.info(f"shop-api booting on port {PORT}")
    threading.Thread(target=_heartbeat, daemon=True).start()
    threading.Thread(target=_synthetic_traffic, daemon=True).start()

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    log.info("shop-api ready — accepting orders")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shop-api shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
