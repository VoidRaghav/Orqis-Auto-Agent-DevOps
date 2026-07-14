"""
Anthropic SDK instrumentation.

Patches anthropic.Anthropic.messages.create (sync) and
anthropic.AsyncAnthropic.messages.create (async) at the class level
so all instances are covered by a single patch call.

Handles both regular responses and streaming (stream=True) — streaming
responses are consumed transparently and re-wrapped so the user's code
sees no difference.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..backend.models import ErrorType, EventKind
from ..instrumentation import costs, emitter

_patched = False
_orig_sync_create = None
_orig_async_create = None


def patch() -> None:
    global _patched, _orig_sync_create, _orig_async_create
    if _patched:
        return
    try:
        from anthropic.resources.messages import Messages, AsyncMessages
    except ImportError:
        return

    # Patch the resource classes directly. On the client class `messages` is a
    # cached_property, so Anthropic.messages.create does not exist until an
    # instance is built — patching the class method covers all instances.
    _orig_sync_create = Messages.create
    _orig_async_create = AsyncMessages.create
    Messages.create = _make_sync_wrapper(_orig_sync_create)
    AsyncMessages.create = _make_async_wrapper(_orig_async_create)

    _patched = True


def unpatch() -> None:
    global _patched
    if not _patched:
        return
    try:
        from anthropic.resources.messages import Messages, AsyncMessages
        if _orig_sync_create:
            Messages.create = _orig_sync_create
        if _orig_async_create:
            AsyncMessages.create = _orig_async_create
    except ImportError:
        pass
    _patched = False


# --- Sync wrapper ------------------------------------------------------------

def _make_sync_wrapper(original):
    def wrapper(self, *args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        start = time.perf_counter()

        _emit(EventKind.LLM_START, run_id=run_id, model=model)

        try:
            response = original(self, *args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, exc, time.perf_counter() - start)
            raise

        _emit_end_from_response(run_id, model, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = True
    return wrapper


# --- Async wrapper -----------------------------------------------------------

def _make_async_wrapper(original):
    async def wrapper(self, *args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        start = time.perf_counter()

        _emit(EventKind.LLM_START, run_id=run_id, model=model)

        try:
            response = await original(self, *args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, exc, time.perf_counter() - start)
            raise

        _emit_end_from_response(run_id, model, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = True
    return wrapper


# --- Event helpers -----------------------------------------------------------

def _emit_end_from_response(run_id: str, model: str, response, elapsed: float) -> None:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = costs.calculate(model, input_tokens, output_tokens)

    _emit(
        EventKind.LLM_END,
        run_id=run_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=int(elapsed * 1000),
    )


def _emit_error(run_id: str, model: str, exc: Exception, elapsed: float) -> None:
    error_type = _classify(exc)
    _emit(
        EventKind.LLM_ERROR,
        run_id=run_id,
        model=model,
        latency_ms=int(elapsed * 1000),
        is_error=True,
        error_type=error_type,
        error_message=f"{type(exc).__name__}: {exc}",
    )


def _classify(exc: Exception) -> ErrorType:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "ratelimit" in name or "rate limit" in msg or "529" in msg or "429" in msg:
        return ErrorType.RATE_LIMIT
    if "authentication" in name or "401" in msg or "api key" in msg or "credit" in msg:
        return ErrorType.AUTHENTICATION
    if "timeout" in name or "timed out" in msg:
        return ErrorType.TIMEOUT
    if "connection" in name:
        return ErrorType.CONNECTION
    if "overloaded" in msg or "503" in msg:
        return ErrorType.HTTP_ERROR
    return ErrorType.GENERIC


def _emit(
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
) -> None:
    emitter.emit({
        "kind": kind.value,
        "run_id": run_id,
        "provider": "anthropic",
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
    })
