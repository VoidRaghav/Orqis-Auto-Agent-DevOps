"""
Thread-safe background event emitter.

The SDK patches run inside the user's thread (could be async, threaded, or
sync). This emitter decouples event delivery from the caller completely:
  - Events are pushed onto a queue (non-blocking, < 1 microsecond)
  - A single background thread drains the queue and POSTs to the backend
  - If the backend is down, events are dropped after MAX_RETRIES — the user's
    agent must never slow down or crash because Orqis is unreachable

Thread model: one daemon thread per process, started on first emit().
The thread is a daemon so it dies automatically when the main process exits.
"""

import json
import logging
import queue
import threading
from typing import Optional

import httpx

from .. import config

logger = logging.getLogger("orqis.emitter")

_queue: queue.Queue = queue.Queue(maxsize=2000)
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()
_shutdown = threading.Event()

MAX_RETRIES = 2
TIMEOUT = 3.0  # seconds — keep it short, never block the user's code


def emit(payload: dict) -> None:
    """
    Enqueue an event for background delivery. Never blocks. Never raises.
    Drops the event silently if the queue is full (backpressure).
    """
    _ensure_started()
    try:
        _queue.put_nowait(payload)
    except queue.Full:
        # Queue full means the backend is likely down — drop and move on
        logger.debug("orqis: event queue full, dropping event")


def shutdown(timeout: float = 5.0) -> None:
    """
    Flush remaining events and stop the background thread.
    Called by orqis.shutdown() — safe to call multiple times.
    """
    _shutdown.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=timeout)


def _ensure_started() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _thread = threading.Thread(target=_worker, name="orqis-emitter", daemon=True)
        _thread.start()


def _worker() -> None:
    """
    Background thread: drain the queue and POST each event to the backend.
    Uses a persistent httpx client for connection reuse.
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        while not (_shutdown.is_set() and _queue.empty()):
            try:
                payload = _queue.get(timeout=0.2)
            except queue.Empty:
                continue

            _post_with_retry(client, payload)
            _queue.task_done()


def _post_with_retry(client: httpx.Client, payload: dict) -> None:
    url = f"{config.BACKEND_URL}/trace"
    headers = {}
    if config.INGEST_API_KEY:
        headers["Authorization"] = f"Bearer {config.INGEST_API_KEY}"
    for attempt in range(MAX_RETRIES + 1):
        try:
            client.post(url, json=payload, headers=headers)
            return
        except httpx.ConnectError:
            # Backend not running — don't retry connection errors, just drop
            return
        except httpx.TimeoutException:
            if attempt == MAX_RETRIES:
                logger.debug("orqis: trace POST timed out after %d retries", MAX_RETRIES)
            return
        except Exception as e:
            logger.debug("orqis: trace POST failed: %s", e)
            return
