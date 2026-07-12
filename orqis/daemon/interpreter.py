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

    if config.LLM_PROVIDER == "anthropic":
        result = await _call_anthropic(raw_line, error_type)
    else:
        result = await _call_ollama(raw_line, error_type)

    _cache[key] = result
    return result


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
    """Call Anthropic Claude Haiku — requires credits."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    context = f"Error type: {error_type.value}\n" if error_type else ""
    user_content = f"{context}Log line:\n{raw_line}"

    try:
        response = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
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


async def check_readiness() -> dict:
    """Probe configured LLM provider — used by /health/ready."""
    provider = config.LLM_PROVIDER
    if provider == "anthropic":
        ok = bool(config.ANTHROPIC_API_KEY)
        return {"ok": ok, "provider": provider, "detail": "api key set" if ok else "missing ANTHROPIC_API_KEY"}
    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                r = await http.get(f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                if r.status_code == 200:
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    want = config.OLLAMA_MODEL
                    has_model = any(want in m for m in models)
                    return {
                        "ok": has_model,
                        "provider": provider,
                        "detail": f"model {want!r} {'found' if has_model else 'not pulled'}",
                    }
                return {"ok": False, "provider": provider, "detail": f"ollama HTTP {r.status_code}"}
        except Exception as exc:
            return {"ok": False, "provider": provider, "detail": str(exc)}
    return {"ok": True, "provider": provider, "detail": "unknown provider — skipped"}
