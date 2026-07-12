"""
Async LLM interpretation layer.

Supports two providers, controlled by config.LLM_PROVIDER:
  - "ollama"     : free, local inference via Ollama (default for dev/demo)
  - "anthropic"  : paid, Claude Haiku (for production)

Cache: identical raw lines skip the LLM call entirely — handles repeated
errors from loops printing the same line hundreds of times.
"""

import hashlib
import sys
from typing import Optional

import httpx

from .. import config
from ..backend.models import ErrorType

# In-memory cache: md5(raw_line) -> interpretation string
_cache: dict[str, str] = {}

# Log the first LLM failure loudly, then stay quiet — silent fallbacks
# hide real problems (expired key, no credits, Ollama down).
_llm_warned = False


def _warn_llm(provider: str, exc: Exception) -> None:
    global _llm_warned
    if _llm_warned:
        return
    _llm_warned = True
    print(
        f"\033[33m[orqis] {provider} LLM unavailable — interpretations and "
        f"patches will fall back to static text. {type(exc).__name__}: {exc}\033[0m",
        file=sys.stderr,
    )

_SYSTEM_PROMPT = (
    "You are an error interpreter for Orqis, a production monitoring tool. "
    "Given a raw server log line that contains an error, respond with exactly "
    "one sentence (maximum 25 words) explaining what went wrong in plain English. "
    "Be direct and specific. Do not hedge. Do not repeat the error name. "
    "Return only the sentence — no prefix, no punctuation beyond the period."
)


def _cache_key(line: str) -> str:
    return hashlib.md5(line.encode(), usedforsecurity=False).hexdigest()


async def interpret(raw_line: str, error_type: Optional[ErrorType] = None) -> str:
    """
    Return a plain-English interpretation of an error log line.
    Uses the cache first, then calls the configured LLM provider.
    Falls back to a static template if all calls fail.
    """
    key = _cache_key(raw_line)
    if key in _cache:
        return _cache[key]

    # Gemini first when configured (one key for the whole LLM layer), then
    # Anthropic if selected, else free local Ollama.
    if config.GEMINI_API_KEY:
        result = await _call_gemini(raw_line, error_type)
    elif config.LLM_PROVIDER == "anthropic":
        result = await _call_anthropic(raw_line, error_type)
    else:
        result = await _call_ollama(raw_line, error_type)

    _cache[key] = result
    return result


async def _call_gemini(raw_line: str, error_type: Optional[ErrorType]) -> str:
    """Call Gemini for a one-line interpretation. Falls back to static text."""
    from .. import llm

    context = f"Error type: {error_type.value}\n" if error_type else ""
    user_content = f"{context}Log line:\n{raw_line}"
    result = await llm.generate(
        user_content, _SYSTEM_PROMPT, config.GEMINI_INTERPRET_MODEL,
        max_tokens=config.LLM_MAX_TOKENS,
    )
    return result if result else _fallback(error_type)


async def _call_ollama(raw_line: str, error_type: Optional[ErrorType]) -> str:
    """Call local Ollama instance — free, no API key required."""
    context = f"Error type: {error_type.value}\n" if error_type else ""
    user_content = f"{context}Log line:\n{raw_line}"

    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {"num_predict": config.LLM_MAX_TOKENS},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{config.OLLAMA_URL}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
    except httpx.ConnectError as e:
        _warn_llm(f"Ollama ({config.OLLAMA_URL})", e)
        return _fallback(error_type)
    except Exception as e:
        _warn_llm("Ollama", e)
        return _fallback(error_type)


async def _call_anthropic(raw_line: str, error_type: Optional[ErrorType]) -> str:
    """Call the Anthropic interpretation model (small/fast) — requires credits."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    context = f"Error type: {error_type.value}\n" if error_type else ""
    user_content = f"{context}Log line:\n{raw_line}"

    try:
        response = await client.messages.create(
            model=config.ANTHROPIC_INTERPRET_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        _warn_llm("Anthropic", e)
        return _fallback(error_type)


# Static fallbacks — used when the LLM call fails or Ollama is not running
_FALLBACKS: dict[ErrorType, str] = {
    ErrorType.RECURSION: "The agent entered an infinite loop and exceeded the maximum call stack depth.",
    ErrorType.MEMORY: "The process ran out of memory and was terminated by the OS.",
    ErrorType.TIMEOUT: "An operation did not complete within the configured time limit.",
    ErrorType.CONNECTION: "The service could not reach a required external endpoint.",
    ErrorType.AUTHENTICATION: "A request was rejected because credentials are invalid or missing.",
    ErrorType.HTTP_ERROR: "A downstream server returned a 4xx or 5xx error response.",
    ErrorType.RATE_LIMIT: "The LLM API rejected the request because the rate limit or quota was exceeded.",
    ErrorType.TOOL_FAILURE: "An agent tool call failed to execute and returned an error.",
    ErrorType.RUNAWAY_LOOP: "The agent kept calling the same tool with no exit condition, burning tokens and money without making progress.",
    ErrorType.CORRUPT_TOOL_OUTPUT: "A tool that normally returns structured data returned an empty payload, and the agent consumed it without validating — corrupting every downstream step with no error raised.",
    ErrorType.COST_SPIKE: "Per-call token usage climbed far above the agent's baseline because its memory is never trimmed — the context, and the bill, grow with every turn while nothing errors.",
    ErrorType.RETRY_STORM: "A tool kept failing with transient errors and was retried with no backoff until it eventually succeeded — the user got an answer, but each call silently cost several times what it should and hammered a struggling API.",
    ErrorType.TOOL_BINDING_DROP: "A tool was bound to the model but the chain returned structured output without ever invoking it — the model filled in valid-looking JSON itself, so the tool's actual work never happened and nothing looked wrong.",
    ErrorType.MULTI_AGENT_PINGPONG: "Two agents handed the task back and forth with no resolver or turn limit, so it bounced between them indefinitely — each agent looked busy and healthy while the orchestration made no progress and burned cost.",
    ErrorType.CONTEXT_OVERFLOW: "The prompt is larger than the model's context window, so the API silently truncates it — usually dropping the system instructions — and the agent answers off-policy with no error raised.",
    ErrorType.PROMPT_INJECTION: "A user input told the agent to ignore its instructions and it obeyed — invoking a tool outside its established, allowed set. The behaviour diverged from the norm with no error raised.",
    ErrorType.AGENT_STUCK: "An operation started and then went silent — the agent is stuck waiting on something that never resolves, making no progress and producing no output, with no error raised.",
    ErrorType.HALLUCINATED_TOOL: "The model invoked a tool that isn't in the registered set — it hallucinated a tool that doesn't exist. The call did no real work, and depending on the setup it either threw or failed silently.",
    ErrorType.WRONG_TOOL: "The agent invoked a destructive or write tool for a read-only request — asked to look something up, it changed or sent something instead. No error was raised, but the wrong, often harmful, action was taken.",
    ErrorType.CASCADE_FAILURE: "One agent produced a degenerate output and a downstream agent consumed it and carried on, so a single bad result poisoned the whole pipeline. Each agent looked fine on its own; only the chain failed.",
    ErrorType.ANOMALY: "This run deviated sharply from the agent's own established baseline — far more calls, tokens, or cost than normal — a symptom of a failure that no specific detector named, possibly a new one.",
    ErrorType.TYPE_ERROR: "A function received an argument of the wrong type.",
    ErrorType.VALUE_ERROR: "A function received an argument with an unacceptable value.",
    ErrorType.ATTRIBUTE_ERROR: "Code attempted to access a property that does not exist on the object.",
    ErrorType.IMPORT_ERROR: "A required Python module could not be found or imported.",
    ErrorType.TRACEBACK: "An unhandled exception was raised. Review the lines above for context.",
    ErrorType.SYNTAX_ERROR: "The code contains a syntax error and could not be parsed.",
    ErrorType.PERMISSION_ERROR: "The process lacks the required OS permissions to perform this operation.",
    ErrorType.GENERIC: "An error occurred. Review the raw log line for details.",
}


def _fallback(error_type: Optional[ErrorType]) -> str:
    if error_type and error_type in _FALLBACKS:
        return _FALLBACKS[error_type]
    return _FALLBACKS[ErrorType.GENERIC]


# Public alias — used by log_reader to set an instant interpretation
# before the async LLM call resolves.
fallback = _fallback
