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

import atexit
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
_atexit_registered = False

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
    global _thread, _atexit_registered
    if _thread is not None and _thread.is_alive():
        return
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _thread = threading.Thread(target=_worker, name="orqis-emitter", daemon=True)
        _thread.start()
        if not _atexit_registered:
            # Short-lived scripts exit before the daemon thread can POST queued
            # events. Flush on interpreter exit so a one-shot run still delivers.
            atexit.register(shutdown)
            _atexit_registered = True


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

            _post(client, payload)
            _queue.task_done()


_warned = False


def _warn_once(msg: str) -> None:
    """Surface the first delivery problem at WARNING, then stay quiet so a
    persistent issue never floods the user's logs."""
    global _warned
    if _warned:
        return
    _warned = True
    logger.warning("orqis: %s (further delivery errors are silenced)", msg)


def _post(client: httpx.Client, payload: dict) -> None:
    url = f"{config.BACKEND_URL}/trace"
    headers = {}
    if config.INGEST_API_KEY:
        headers["Authorization"] = f"Bearer {config.INGEST_API_KEY}"
    try:
        resp = client.post(url, json=payload, headers=headers)
    except httpx.ConnectError:
        _warn_once(f"cannot reach backend at {config.BACKEND_URL} - is it running?")
        return
    except httpx.TimeoutException:
        _warn_once(f"trace POST to {config.BACKEND_URL} timed out")
        return
    except Exception as e:
        _warn_once(f"trace POST failed: {e}")
        return
    if resp.status_code >= 400:
        detail = resp.text[:200].replace("\n", " ")
        if resp.status_code in (401, 403):
            _warn_once(
                f"backend rejected trace (HTTP {resp.status_code}) - "
                f"check your ORQIS_API_KEY: {detail}"
            )
        else:
            _warn_once(f"backend returned HTTP {resp.status_code}: {detail}")
