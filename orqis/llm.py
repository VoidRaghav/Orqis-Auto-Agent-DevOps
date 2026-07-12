"""
Shared LLM helper for Google Gemini.

Gemini is called over the Generative Language REST API with httpx (already a
dependency), so there is no extra SDK to install. Both the interpreter (one-line
summaries) and the patch generator (code fixes) use this — the model is chosen
per call site. Every failure returns None so the caller can fall back cleanly;
this helper never raises.
"""

import sys
from typing import Optional

import httpx

from . import config

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def enabled() -> bool:
    return bool(config.GEMINI_API_KEY)


async def generate(
    prompt: str,
    system: str,
    model: str,
    max_tokens: int = 8192,
    temperature: float = 0.2,
    timeout: float = 60.0,
) -> Optional[str]:
    """Return the model's text output, or None on any failure/empty/blocked."""
    if not config.GEMINI_API_KEY:
        return None

    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                _ENDPOINT.format(model=model),
                headers={
                    "x-goog-api-key": config.GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            return _extract_text(resp.json())
    except Exception as e:
        _warn("Gemini", e)
        return None


async def openai_chat(
    prompt: str,
    system: str,
    base_url: str,
    api_key: str,
    model: str,
    provider: str = "OpenAI-compatible",
    max_tokens: int = 8192,
    temperature: float = 0.2,
    timeout: float = 60.0,
) -> Optional[str]:
    """
    Call any OpenAI-compatible chat endpoint (Groq, OpenAI, etc.). Returns the
    message text, or None on any failure — so the caller can fall through to the
    next provider. Never raises.
    """
    if not api_key:
        return None

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            choices = resp.json().get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content")
                return content.strip() if content else None
            return None
    except Exception as e:
        _warn(provider, e)
        return None


def _extract_text(data: dict) -> Optional[str]:
    """Pull the concatenated text from the first candidate, or None if blocked."""
    for cand in data.get("candidates", []):
        parts = cand.get("content", {}).get("parts", [])
        texts = [p["text"] for p in parts if isinstance(p, dict) and "text" in p]
        if texts:
            return "".join(texts).strip()
    return None


def _warn(provider: str, err: Exception) -> None:
    detail = str(err)
    if isinstance(err, httpx.HTTPStatusError):
        detail = f"{err.response.status_code} {err.response.text[:200]}"
    print(
        f"\033[33m[orqis] {provider} LLM unavailable — falling back. "
        f"{type(err).__name__}: {detail}\033[0m",
        file=sys.stderr,
    )
