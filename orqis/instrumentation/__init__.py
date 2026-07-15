"""
Orqis SDK instrumentation layer.

This module is the single entry point. Calling init() installs all patches
that are applicable for the libraries currently installed in the environment.
Libraries not installed are skipped silently — no ImportError is ever raised.

Usage:
    import orqis
    orqis.init(api_key="orqs_your_key")

    # All subsequent LangChain / OpenAI / Anthropic calls are auto-captured.
    # Nothing else changes in your code.
"""

import logging
import os
from typing import Optional

from ..instrumentation import emitter
from ..instrumentation.langchain_patch import OrqisCallbackHandler

logger = logging.getLogger("orqis")

# The LangChain handler is kept as a module-level ref so users can also
# pass it manually: chain.invoke(..., config={"callbacks": [orqis.callback]})
callback: Optional[OrqisCallbackHandler] = None

_initialized = False


def init(
    api_key: Optional[str] = None,
    backend_url: Optional[str] = None,
    source: str = "sdk",
    capture_logs: bool = True,
    heartbeat: bool = True,
) -> None:
    """
    Initialize Orqis instrumentation.

    Args:
        api_key:      Orqis project API key (or set ORQIS_API_KEY env var).
        backend_url:  Override the backend URL (default: http://localhost:8000).
        source:       Label shown on the dashboard for all events from this process.
        capture_logs: Stream the app's own log lines to the Activity feed
                      (INFO and above). Set False to send LLM traces only.
        heartbeat:    Ping the backend every ~15s so the dashboard shows the
                      agent as up (and as down if the process dies). Set False
                      to disable liveness pings.
    """
    global _initialized, callback

    if _initialized:
        return

    from .. import config

    # Allow env var as fallback for api_key (standard 12-factor pattern)
    resolved_key = api_key or os.getenv("ORQIS_API_KEY", "")
    if resolved_key:
        config.INGEST_API_KEY = resolved_key
    if backend_url:
        config.BACKEND_URL = backend_url

    # Install SDK patches — each is skipped if that library is not installed.
    patched = []
    if _patch_openai():
        patched.append("openai")
    if _patch_anthropic():
        patched.append("anthropic")
    callback = _register_langchain()
    if callback is not None and _langchain_available():
        patched.append("langchain")

    if capture_logs:
        from ..instrumentation import logs
        logs.install(source=source)

    if heartbeat:
        from ..instrumentation import heartbeat as hb
        hb.start(source=source)

    _initialized = True

    # One concise line so users can see what was detected and where events go.
    logger.info(
        "orqis active: capturing [%s], logs=%s, heartbeat=%s, backend=%s, api_key=%s (source=%s)",
        ", ".join(patched) if patched else "none detected",
        "on" if capture_logs else "off",
        "on" if heartbeat else "off",
        config.BACKEND_URL,
        "set" if config.INGEST_API_KEY else "MISSING",
        source,
    )
    if not patched:
        logger.warning(
            "orqis: no supported LLM library detected (openai / anthropic / "
            "langchain) at init() time"
        )


def shutdown() -> None:
    """
    Flush pending events and stop the background emitter thread.
    Call this at the end of your script for a clean exit.
    Calling multiple times is safe.
    """
    global _initialized
    from ..instrumentation import heartbeat as hb
    from ..instrumentation import logs
    hb.stop()
    logs.uninstall()
    emitter.shutdown()
    _initialized = False


def _langchain_available() -> bool:
    import importlib.util

    return (
        importlib.util.find_spec("langchain_core") is not None
        or importlib.util.find_spec("langchain") is not None
    )


def _patch_openai() -> bool:
    try:
        from ..instrumentation import openai_patch
        openai_patch.patch()
        return openai_patch._patched
    except Exception as e:
        logger.debug("orqis: OpenAI patch skipped (%s)", e)
        return False


def _patch_anthropic() -> bool:
    try:
        from ..instrumentation import anthropic_patch
        anthropic_patch.patch()
        return anthropic_patch._patched
    except Exception as e:
        logger.debug("orqis: Anthropic patch skipped (%s)", e)
        return False


def _register_langchain() -> Optional[OrqisCallbackHandler]:
    try:
        from ..instrumentation.langchain_patch import register
        handler = register()
        logger.debug("orqis: LangChain callback handler registered")
        return handler
    except Exception as e:
        logger.debug("orqis: LangChain registration skipped (%s)", e)
        return None
