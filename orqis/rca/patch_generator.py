"""
LLM-powered patch generator.

Takes an error + its code context (from file_reader.py) and produces a
unified diff string that can be applied with `patch` or shown in a diff panel.

Flow:
  1. Build a focused prompt: error message + minimal code context only.
  2. Call Ollama (free) or Anthropic (paid) — same config as interpreter.py.
  3. Parse the LLM output: extract the diff block, validate it is a legal
     unified diff before storing. Reject and return None if invalid.
  4. Never write to disk — the caller stores the diff and waits for approval.

Cost: ~300-600 input tokens + ~200 output tokens per patch call.
  Ollama: $0
  Haiku:  ~$0.003 per patch (only fires on real errors with tracebacks)
"""

import re
from typing import Optional

import httpx

from .. import config
from ..rca.file_reader import CodeLocation

_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

Given an error and the source code where it occurred, produce the minimal \
unified diff that fixes the root cause. Rules:
- Output ONLY the unified diff — no explanation, no markdown fences, nothing else.
- Use standard unified diff format: --- a/file, +++ b/file, @@ ... @@
- Make the smallest possible change that fixes the bug.
- Do not reformat, rename, or refactor unrelated code.
- If the fix requires an import, add it.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""


async def generate(
    error_message: str,
    location: CodeLocation,
) -> Optional[str]:
    """
    Generate a unified diff for the given error and code location.
    Returns the diff string, or None if no safe fix could be produced.
    Never raises — any failure returns None.
    """
    prompt = _build_prompt(error_message, location)

    if config.LLM_PROVIDER == "anthropic":
        raw = await _call_anthropic(prompt)
    else:
        raw = await _call_ollama(prompt)

    if raw is None:
        return None

    return _extract_and_validate_diff(raw, location.file_path)


def _build_prompt(error_message: str, location: CodeLocation) -> str:
    func_label = f"function `{location.function_name}`" if location.function_name else "module-level code"
    return (
        f"Error:\n{error_message}\n\n"
        f"File: {location.file_path}\n"
        f"Error at line: {location.line}\n"
        f"Context ({func_label}, starting at line {location.context_start_line}):\n"
        f"```python\n{location.context}\n```\n\n"
        f"Generate the unified diff to fix this error."
    )


async def _call_ollama(prompt: str) -> Optional[str]:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # Patches are short — cap tokens to avoid runaway generation
        "options": {"num_predict": 400},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        return None  # Ollama not running
    except Exception:
        return None


async def _call_anthropic(prompt: str) -> Optional[str]:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None


# Unified diff header pattern — must be present for a valid diff
_DIFF_HEADER = re.compile(r"^---\s+\S+.*\n\+\+\+\s+\S+", re.MULTILINE)
_HUNK_HEADER = re.compile(r"^@@\s+-\d+", re.MULTILINE)

# Strip markdown code fences if the LLM wrapped the diff in them
_CODE_FENCE = re.compile(r"```(?:diff|patch)?\n(.*?)```", re.DOTALL)


def _extract_and_validate_diff(raw: str, file_path: str) -> Optional[str]:
    """
    Extract a unified diff from the LLM output and validate it.
    Returns None if the output is not a valid diff or is NO_FIX.
    """
    if raw.strip() == "NO_FIX" or not raw.strip():
        return None

    # Strip markdown fences if present
    fence_match = _CODE_FENCE.search(raw)
    diff = fence_match.group(1).strip() if fence_match else raw.strip()

    # Must have both a header and at least one hunk
    if not _DIFF_HEADER.search(diff):
        # LLM may have skipped the --- +++ header — inject it and retry validation
        diff = f"--- a/{file_path}\n+++ b/{file_path}\n{diff}"

    if not _HUNK_HEADER.search(diff):
        # No hunk headers — not a valid diff
        return None

    # Every line must start with ' ', '+', '-', '@', or '\' (no-newline marker)
    for line in diff.splitlines():
        if line and line[0] not in (" ", "+", "-", "@", "\\", "#"):
            # LLM added prose — strip it and continue
            diff = "\n".join(
                l for l in diff.splitlines()
                if not l or l[0] in (" ", "+", "-", "@", "\\", "#")
            )
            break

    return diff if diff.strip() else None
