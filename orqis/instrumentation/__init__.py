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
) -> None:
    """
    Initialize Orqis instrumentation.

    Args:
        api_key:     Orqis project API key (or set ORQIS_API_KEY env var).
        backend_url: Override the backend URL (default: http://localhost:8000).
        source:      Label shown on the dashboard for all events from this process.
    """
    global _initialized, callback

    if _initialized:
        return

    # Allow env var as fallback for api_key (standard 12-factor pattern)
    resolved_key = api_key or os.getenv("ORQIS_API_KEY", "")
    if resolved_key:
        from .. import config
        config.INGEST_API_KEY = resolved_key

    # Override config values if provided
    if backend_url:
        from .. import config
        config.BACKEND_URL = backend_url

    # Install SDK patches — each is silently skipped if the lib isn't installed
    _patch_openai()
    _patch_anthropic()
    callback = _register_langchain()

    _initialized = True
    logger.debug("orqis: instrumentation active (source=%s)", source)


def shutdown() -> None:
    """
    Flush pending events and stop the background emitter thread.
    Call this at the end of your script for a clean exit.
    Calling multiple times is safe.
    """
    global _initialized
    emitter.shutdown()
    _initialized = False


def _patch_openai() -> None:
    try:
        from ..instrumentation.openai_patch import patch
        patch()
        logger.debug("orqis: OpenAI SDK patched")
    except Exception as e:
        logger.debug("orqis: OpenAI patch skipped (%s)", e)


def _patch_anthropic() -> None:
    try:
        from ..instrumentation.anthropic_patch import patch
        patch()
        logger.debug("orqis: Anthropic SDK patched")
    except Exception as e:
        logger.debug("orqis: Anthropic patch skipped (%s)", e)


def _register_langchain() -> Optional[OrqisCallbackHandler]:
    try:
        from ..instrumentation.langchain_patch import register
        handler = register()
        logger.debug("orqis: LangChain callback handler registered")
        return handler
    except Exception as e:
        logger.debug("orqis: LangChain registration skipped (%s)", e)
        return None
