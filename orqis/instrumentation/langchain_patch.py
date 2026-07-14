"""
LangChain instrumentation via the native callback system.

LangChain exposes a BaseCallbackHandler interface — no monkey-patching needed.
We register one OrqisCallbackHandler globally so it fires on every chain, LLM
call, and tool call without any change to the user's agent code.

Supports LangChain >= 0.1 (callback handler API is stable across versions).
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from ..backend.models import ErrorType, EventKind
from ..instrumentation import costs, emitter

# run_id -> start time (perf_counter), used to compute latency on *_end events
_active_runs: dict[str, float] = {}


class OrqisCallbackHandler:
    """
    LangChain callback handler. Registered once via langchain.callbacks.set_handler()
    or passed as a callback to any chain/agent.

    Each handler method is called by LangChain on the main execution thread
    synchronously — all we do is enqueue an event, which is < 1 microsecond.
    """

    # LangChain checks for this attribute to decide if the handler is async
    is_async = False

    # --- LLM events ----------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict,
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        _active_runs[rid] = time.perf_counter()
        model = _extract_model(serialized)
        _emit(EventKind.LLM_START, run_id=rid, model=model)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        model = _model_from_response(response)

        # Extract token usage from LLMResult
        input_tokens, output_tokens, cost = None, None, None
        try:
            usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            if model and input_tokens is not None and output_tokens is not None:
                cost = costs.calculate(model, input_tokens, output_tokens)
        except Exception:
            pass

        _emit(
            EventKind.LLM_END,
            run_id=rid,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=elapsed,
        )

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        error_type = _classify(error)
        _emit(
            EventKind.LLM_ERROR,
            run_id=rid,
            latency_ms=elapsed,
            is_error=True,
            error_type=error_type,
            error_message=f"{type(error).__name__}: {error}",
        )

    # --- Tool events ---------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        _active_runs[rid] = time.perf_counter()
        tool_name = serialized.get("name", "unknown")
        _emit(EventKind.TOOL_START, run_id=rid, model=tool_name)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        _emit(EventKind.TOOL_END, run_id=rid, latency_ms=elapsed)

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        _emit(
            EventKind.TOOL_ERROR,
            run_id=rid,
            latency_ms=elapsed,
            is_error=True,
            error_type=ErrorType.TOOL_FAILURE,
            error_message=f"{type(error).__name__}: {error}",
        )

    # --- Chain events --------------------------------------------------------

    def on_chain_start(
        self,
        serialized: dict,
        inputs: dict,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        _active_runs[rid] = time.perf_counter()
        _emit(EventKind.CHAIN_START, run_id=rid)

    def on_chain_end(
        self,
        outputs: dict,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        _emit(EventKind.CHAIN_END, run_id=rid, latency_ms=elapsed)

    def on_chain_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        rid = str(run_id)
        elapsed = _pop_elapsed(rid)
        error_type = _classify(error)
        _emit(
            EventKind.CHAIN_ERROR,
            run_id=rid,
            latency_ms=elapsed,
            is_error=True,
            error_type=error_type,
            error_message=f"{type(error).__name__}: {error}",
        )

    # LangChain requires these even if unused
    def on_agent_action(self, *args, **kwargs): pass
    def on_agent_finish(self, *args, **kwargs): pass
    def on_text(self, *args, **kwargs): pass


def register() -> Optional[OrqisCallbackHandler]:
    """
    Attempt to register the handler globally in LangChain.
    Returns the handler instance (can also be passed manually to any chain).
    Returns None if LangChain is not installed.
    """
    handler = OrqisCallbackHandler()
    try:
        from langchain.callbacks import set_handler
        set_handler(handler)
    except ImportError:
        pass  # LangChain not installed — handler still usable manually
    except Exception:
        pass  # Older LangChain without set_handler — user passes it manually
    return handler


# --- Helpers -----------------------------------------------------------------

def _pop_elapsed(run_id: str) -> Optional[int]:
    start = _active_runs.pop(run_id, None)
    if start is None:
        return None
    return int((time.perf_counter() - start) * 1000)


def _extract_model(serialized: dict) -> Optional[str]:
    # LangChain puts the model name in different places depending on the LLM class
    return (
        serialized.get("kwargs", {}).get("model_name")
        or serialized.get("kwargs", {}).get("model")
        or serialized.get("name")
    )


def _model_from_response(response: Any) -> Optional[str]:
    try:
        return response.llm_output.get("model_name") if response.llm_output else None
    except Exception:
        return None


def _classify(exc: Exception) -> ErrorType:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "recursion" in name or "recursion" in msg:
        return ErrorType.RECURSION
    if "ratelimit" in name or "rate limit" in msg or "429" in msg:
        return ErrorType.RATE_LIMIT
    if "timeout" in name or "timed out" in msg:
        return ErrorType.TIMEOUT
    if "connection" in name:
        return ErrorType.CONNECTION
    if "toolexception" in name or "tool" in name:
        return ErrorType.TOOL_FAILURE
    if "valueerror" in name:
        return ErrorType.VALUE_ERROR
    if "typeerror" in name:
        return ErrorType.TYPE_ERROR
    if "attributeerror" in name:
        return ErrorType.ATTRIBUTE_ERROR
    return ErrorType.GENERIC


def _emit(
    kind: EventKind,
    run_id: str,
    model: Optional[str] = None,
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
        "provider": "langchain",
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
