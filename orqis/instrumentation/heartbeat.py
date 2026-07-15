"""
Liveness heartbeat.

While the agent process is running, a daemon thread pings the backend every
INTERVAL seconds so the dashboard can show the agent is up - even when it is
idle between jobs and emitting no logs. If the pings stop (crash, kill, network
loss), the backend key expires and the agent is shown as down.

The ping is tiny and best-effort: failures are swallowed so the agent is never
affected by Orqis being unreachable.
"""

import logging
import threading

import httpx

from .. import config

logger = logging.getLogger("orqis.heartbeat")

INTERVAL = 15.0  # seconds between pings
TIMEOUT = 3.0

_thread = None
_stop = threading.Event()


def start(source: str = "sdk", interval: float = INTERVAL) -> None:
    """Start the heartbeat thread. Idempotent."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_loop, args=(source, interval), name="orqis-heartbeat", daemon=True
    )
    _thread.start()


def stop() -> None:
    _stop.set()


def _loop(source: str, interval: float) -> None:
    url = f"{config.BACKEND_URL}/heartbeat"
    with httpx.Client(timeout=TIMEOUT) as client:
        # Ping immediately so "up" shows the moment the agent starts, then repeat.
        while not _stop.is_set():
            headers = {}
            if config.INGEST_API_KEY:
                headers["Authorization"] = f"Bearer {config.INGEST_API_KEY}"
            try:
                client.post(url, json={"source": source}, headers=headers)
            except Exception as e:
                logger.debug("orqis: heartbeat failed (%s)", e)
            _stop.wait(interval)
