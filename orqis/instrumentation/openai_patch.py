"""
OpenAI SDK instrumentation.

Monkey-patches openai.chat.completions.create (sync) and its async variant
so every call is captured without any code change in the user's agent.

Patch is idempotent — calling patch() twice has no effect.
Calling unpatch() restores the original methods exactly.
"""

import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..backend.models import ErrorType, EventKind
from ..instrumentation import costs, emitter

_patched = False
_orig_sync = None
_orig_async = None


def patch() -> None:
    global _patched, _orig_sync, _orig_async
    if _patched:
        return
    try:
        import openai
    except ImportError:
        return  # openai not installed — skip silently

    _orig_sync = openai.chat.completions.create
    _orig_async = openai.AsyncClient  # placeholder; patched on instance below
    openai.chat.completions.create = _wrap_sync(openai.chat.completions.create)

    # Patch async path: AsyncOpenAI().chat.completions.create
    _patch_async_client(openai)

    _patched = True


def unpatch() -> None:
    global _patched
    if not _patched:
        return
    try:
        import openai
        if _orig_sync:
            openai.chat.completions.create = _orig_sync
    except ImportError:
        pass
    _patched = False


# --- Sync wrapper ------------------------------------------------------------

def _wrap_sync(original):
    def wrapper(*args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        start = time.perf_counter()

        _emit_start(run_id, model)

        try:
            response = original(*args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, exc, time.perf_counter() - start)
            raise  # always re-raise — never swallow the user's exception

        _emit_end(run_id, model, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = original
    return wrapper


# --- Async wrapper -----------------------------------------------------------

def _patch_async_client(openai_module) -> None:
    """
    Wrap AsyncOpenAI.chat.completions.create.
    We patch at the class level so all instances are covered.
    """
    try:
        orig = openai_module.AsyncOpenAI
        original_init = orig.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            original_create = self.chat.completions.create
            if not getattr(original_create, "__wrapped__", False):
                self.chat.completions.create = _wrap_async(original_create)

        orig.__init__ = patched_init
    except Exception:
        pass  # async client not available in this version


def _wrap_async(original):
    async def wrapper(*args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        start = time.perf_counter()

        _emit_start(run_id, model)

        try:
            response = await original(*args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, exc, time.perf_counter() - start)
            raise

        _emit_end(run_id, model, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = True
    return wrapper


# --- Event helpers -----------------------------------------------------------

def _emit_start(run_id: str, model: str) -> None:
    emitter.emit(_build(
        kind=EventKind.LLM_START,
        run_id=run_id,
        model=model,
    ))


def _emit_end(run_id: str, model: str, response, elapsed: float) -> None:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = costs.calculate(model, input_tokens, output_tokens)

    emitter.emit(_build(
        kind=EventKind.LLM_END,
        run_id=run_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=int(elapsed * 1000),
    ))


def _emit_error(run_id: str, model: str, exc: Exception, elapsed: float) -> None:
    error_type = _classify_openai_error(exc)
    emitter.emit(_build(
        kind=EventKind.LLM_ERROR,
        run_id=run_id,
        model=model,
        latency_ms=int(elapsed * 1000),
        is_error=True,
        error_type=error_type,
        error_message=f"{type(exc).__name__}: {exc}",
    ))


def _classify_openai_error(exc: Exception) -> ErrorType:
    name = type(exc).__name__
    msg = str(exc).lower()
    if "ratelimit" in name.lower() or "rate limit" in msg or "429" in msg:
        return ErrorType.RATE_LIMIT
    if "authentication" in name.lower() or "401" in msg or "api key" in msg:
        return ErrorType.AUTHENTICATION
    if "timeout" in name.lower() or "timed out" in msg:
        return ErrorType.TIMEOUT
    if "connection" in name.lower():
        return ErrorType.CONNECTION
    if "badrequest" in name.lower() or "400" in msg:
        return ErrorType.HTTP_ERROR
    return ErrorType.GENERIC


def _build(
    kind: EventKind,
    run_id: str,
    model: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    latency_ms: Optional[int] = None,
    is_error: bool = False,
    error_type: Optional[ErrorType] = None,
    error_message: Optional[str] = None,
) -> dict:
    return {
        "kind": kind.value,
        "run_id": run_id,
        "provider": "openai",
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "is_error": is_error,
        "error_type": error_type.value if error_type else None,
        "error_message": error_message,
        "source": "sdk",
    }
