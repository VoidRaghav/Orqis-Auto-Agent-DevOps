"""
Log bridge.

Attaches a handler to the root logger so the agent's own log lines (its HTTP
requests, info/warn/error messages, tracebacks) are streamed to Orqis and shown
in the dashboard Activity feed — the same lines the developer sees in the
terminal. Nothing about the app's logging behaviour changes; this only adds a
listener.

Two records are never captured, to avoid an infinite loop:
  - anything from the "orqis" logger namespace (our own diagnostics)
  - any line mentioning the Orqis backend URL (the SDK's own POSTs, which the
    httpx logger emits for every /trace and /ingest request)
"""

import logging

from .. import config
from ..instrumentation import emitter

_LINE_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_handler = None


class _OrqisLogHandler(logging.Handler):
    def __init__(self, source: str, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._source = source
        self.setFormatter(logging.Formatter(_LINE_FORMAT, datefmt=_DATE_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if (record.name or "").startswith("orqis"):
                return
            # Break the feedback loop: skip the SDK's own backend requests.
            if config.BACKEND_URL and config.BACKEND_URL in record.getMessage():
                return
            emitter.emit_log(self.format(record), source=self._source)
        except Exception:
            # A logging handler must never raise into the caller.
            pass


def install(source: str = "sdk", level: int = logging.INFO) -> None:
    """Attach the log handler to the root logger. Idempotent."""
    global _handler
    if _handler is not None:
        return
    _handler = _OrqisLogHandler(source=source, level=level)
    logging.getLogger().addHandler(_handler)


def uninstall() -> None:
    global _handler
    if _handler is None:
        return
    logging.getLogger().removeHandler(_handler)
    _handler = None
