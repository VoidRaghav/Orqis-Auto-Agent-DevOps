"""
OpenAI SDK instrumentation.

Monkey-patches the Completions.create / AsyncCompletions.create resource
methods at the class level, so every OpenAI client instance is captured
without any code change in the user's agent.

Patch is idempotent — calling patch() twice has no effect.
Calling unpatch() restores the original methods exactly.
"""

import time
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
        from openai.resources.chat.completions import Completions, AsyncCompletions
    except ImportError:
        return  # openai not installed (or unexpected layout) — skip silently

    # Patch at the class level so every client instance is covered. Modern
    # openai (>=1.0) is used as OpenAI().chat.completions.create(...), which
    # resolves to Completions.create — patching the module singleton misses it.
    _orig_sync = Completions.create
    _orig_async = AsyncCompletions.create
    Completions.create = _wrap_sync(_orig_sync)
    AsyncCompletions.create = _wrap_async(_orig_async)

    _patched = True


def unpatch() -> None:
    global _patched
    if not _patched:
        return
    try:
        from openai.resources.chat.completions import Completions, AsyncCompletions
        if _orig_sync:
            Completions.create = _orig_sync
        if _orig_async:
            AsyncCompletions.create = _orig_async
    except ImportError:
        pass
    _patched = False


# --- Sync wrapper ------------------------------------------------------------

def _wrap_sync(original):
    def wrapper(self, *args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        provider = _detect_provider(self)
        start = time.perf_counter()

        _emit_start(run_id, model, provider)

        try:
            response = original(self, *args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, provider, exc, time.perf_counter() - start)
            raise  # always re-raise — never swallow the user's exception

        _emit_end(run_id, model, provider, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = original
    return wrapper


# --- Async wrapper -----------------------------------------------------------

def _wrap_async(original):
    async def wrapper(self, *args, **kwargs):
        run_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        provider = _detect_provider(self)
        start = time.perf_counter()

        _emit_start(run_id, model, provider)

        try:
            response = await original(self, *args, **kwargs)
        except Exception as exc:
            _emit_error(run_id, model, provider, exc, time.perf_counter() - start)
            raise

        _emit_end(run_id, model, provider, response, time.perf_counter() - start)
        return response

    wrapper.__wrapped__ = original
    return wrapper


# --- Provider detection ------------------------------------------------------

# Base-URL fragments mapped to a friendly provider name. The openai package is a
# universal client for OpenAI-compatible backends, so the real provider is
# whatever the client's base_url points at — not always "openai".
_PROVIDER_HOSTS = (
    ("api.openai.com", "openai"),
    ("11434", "ollama"),
    ("ollama", "ollama"),
    ("groq.com", "groq"),
    ("generativelanguage.googleapis.com", "gemini"),
    ("openrouter.ai", "openrouter"),
    ("api.anthropic.com", "anthropic"),
    ("api.mistral.ai", "mistral"),
    ("api.together.xyz", "together"),
    ("api.deepseek.com", "deepseek"),
    ("api.perplexity.ai", "perplexity"),
    ("openai.azure.com", "azure"),
)


def _detect_provider(resource) -> str:
    """Derive the real provider from the client's base_url."""
    try:
        base = str(getattr(resource._client, "base_url", "") or "").lower()
    except Exception:
        base = ""
    if not base:
        return "openai"
    for fragment, name in _PROVIDER_HOSTS:
        if fragment in base:
            return name
    # Unknown OpenAI-compatible endpoint: surface the host rather than mislabel.
    try:
        from urllib.parse import urlparse

        host = urlparse(base).netloc.split(":")[0]
        return host or "openai-compatible"
    except Exception:
        return "openai-compatible"


# --- Event helpers -----------------------------------------------------------

def _emit_start(run_id: str, model: str, provider: str) -> None:
    emitter.emit(_build(
        kind=EventKind.LLM_START,
        run_id=run_id,
        model=model,
        provider=provider,
    ))


def _emit_end(run_id: str, model: str, provider: str, response, elapsed: float) -> None:
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
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=int(elapsed * 1000),
    ))


def _emit_error(run_id: str, model: str, provider: str, exc: Exception, elapsed: float) -> None:
    error_type = _classify_openai_error(exc)
    emitter.emit(_build(
        kind=EventKind.LLM_ERROR,
        run_id=run_id,
        model=model,
        provider=provider,
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
    provider: str = "openai",
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
        "provider": provider,
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
