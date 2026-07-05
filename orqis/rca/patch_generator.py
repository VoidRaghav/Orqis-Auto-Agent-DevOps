"""
LLM-powered patch generator.

Takes an error + its code context (from file_reader.py) and produces a unified
diff string that the verification gates can check and the dashboard can show.

Why we don't ask the model for a diff:
  Small local models write correct Python but cannot reliably hand-author
  unified-diff syntax — they miscount @@ line numbers, drop indentation, and
  emit stray markers, so the patch fails the hallucination gate even when the
  fix is right. Instead we ask for the corrected code block and compute the
  diff ourselves with difflib against the real file. The removed lines are then
  taken verbatim from the source, so a patch can never hallucinate a deletion;
  the only ways to fail are bad Python or unsafe imports, which the gates catch.

Flow:
  1. Build a focused prompt: error + the exact code block to repair.
  2. Call Claude Opus (when a key is set) or local Ollama as a fallback.
  3. Splice the returned block back into the file and difflib the result.
  4. Never write to disk — the caller stores the diff and waits for approval.

Model choice: patching is correctness-critical, so it uses the strongest model
(Claude Opus by default) with adaptive thinking, independent of the cheaper
interpretation model. The reasoning stays in thinking blocks so the visible
answer is a clean code block.

Cost: ~3k-8k input tokens + ~1k-3k output tokens per patch call.
  Ollama: $0
  Opus 4.8: ~$0.05-0.15 per patch (deterministic fixes cost $0)
"""

import difflib
import re
from typing import Optional

import httpx

from .. import config
from ..daemon.interpreter import _warn_llm
from ..rca.file_reader import CodeLocation

_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

You are given an error and the exact block of source code where it occurred. \
Return the COMPLETE corrected version of that same block. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end, changing only what is \
needed to fix the root cause.
- Preserve every other line exactly, including indentation and blank lines.
- Do not rename or refactor unrelated code.
- If the fix needs an import, add it inside the block if that is valid, \
otherwise leave it out.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Loop fixes are structural, not syntactic — the code parses and runs fine, it
# just never stops. Steer the model toward a bounded-retry guard instead of
# hunting for a typo that isn't there.
_LOOP_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below runs without error but loops forever: it calls a tool \
repeatedly with no exit condition, burning money. Return the COMPLETE corrected \
version of that same block with a bounded-retry guard added. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Add a maximum attempt count; when it is reached, stop looping and return a \
safe fallback value (escalate to a human / give up gracefully). Do NOT raise.
- Keep the normal-case behaviour unchanged — only add the cap.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""


async def generate(
    error_message: str,
    location: CodeLocation,
    kind: str = "error",
) -> Optional[str]:
    """
    Generate a unified diff for the given error and code location.

    kind="error" fixes a raised exception; kind="loop" adds a bounded-retry
    guard to a no-exit-condition agent loop. Returns the diff string, or None
    if no safe fix could be produced. Never raises — any failure returns None.
    """
    prompt = _build_prompt(error_message, location)
    system = _LOOP_SYSTEM_PROMPT if kind == "loop" else _SYSTEM_PROMPT

    # Always prefer Claude Opus for patches when a key is available — correctness
    # here is worth far more than the per-patch cost. Fall back to local Ollama
    # on any failure, or when no key is configured.
    if config.ANTHROPIC_API_KEY:
        raw = await _call_anthropic(prompt, system)
        if raw is None:
            raw = await _call_ollama(prompt, system)
    else:
        raw = await _call_ollama(prompt, system)

    if raw is None:
        return None

    return _diff_from_rewrite(raw, location)


def _build_prompt(error_message: str, location: CodeLocation) -> str:
    func_label = f"function `{location.function_name}`" if location.function_name else "module-level code"
    return (
        f"Error:\n{error_message}\n\n"
        f"File: {location.file_path}\n"
        f"Error at line: {location.line}\n"
        f"Code block to repair ({func_label}, lines "
        f"{location.context_start_line}-{location.context_start_line + len(location.context.splitlines()) - 1}):\n"
        f"```python\n{location.context}\n```\n\n"
        f"Return the complete corrected code block."
    )


async def _call_ollama(prompt: str, system: str) -> Optional[str]:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # A corrected function is longer than a diff — give it room but still cap.
        "options": {"num_predict": 600},
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError as e:
        _warn_llm(f"Ollama ({config.OLLAMA_URL})", e)
        return None
    except Exception as e:
        _warn_llm("Ollama", e)
        return None


async def _call_anthropic(prompt: str, system: str) -> Optional[str]:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=config.ANTHROPIC_PATCH_MODEL,
            max_tokens=8192,
            system=system,
            # Adaptive thinking keeps the reasoning in thinking blocks, so the
            # visible answer stays a clean code block; high effort favours a
            # correct patch over token savings.
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=[{"role": "user", "content": prompt}],
        )
        return _text_block(response)
    except Exception as e:
        _warn_llm("Anthropic", e)
        return None


def _text_block(response) -> Optional[str]:
    """Return the assistant's text output, skipping any thinking blocks."""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text.strip()
    return None


# Strip a markdown code fence if the model wrapped its answer in one.
_CODE_FENCE = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)


def _diff_from_rewrite(raw: str, location: CodeLocation) -> Optional[str]:
    """
    Splice the model's corrected block back into the real file and compute a
    unified diff with difflib. Because the removed lines come straight from the
    source, the resulting diff is guaranteed to apply — the gates then judge the
    Python itself, not the diff formatting.
    """
    fence = _CODE_FENCE.search(raw)
    code = (fence.group(1) if fence else raw).strip("\n")

    if not code.strip() or code.strip() == "NO_FIX":
        return None

    # Prefer in-memory source (fetched from GitHub) so we never touch the local
    # filesystem on the server path; fall back to disk read for local dev.
    if location.source_text is not None:
        original = location.source_text
    else:
        try:
            with open(location.file_path, "r", encoding="utf-8") as f:
                original = f.read()
        except OSError:
            return None

    orig_lines = original.splitlines()
    start = location.context_start_line - 1          # 0-indexed slice start
    end = start + len(location.context.splitlines())  # exclusive slice end
    if start < 0 or end > len(orig_lines):
        return None

    new_region = code.splitlines()
    if not new_region:
        return None

    patched_lines = orig_lines[:start] + new_region + orig_lines[end:]
    if patched_lines == orig_lines:
        return None  # model returned the block unchanged

    # Diff headers use the repo-relative path when available so the diff applies
    # and commits cleanly through the GitHub API (R2).
    header_path = location.repo_relative_path or location.file_path
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            patched_lines,
            fromfile=f"a/{header_path}",
            tofile=f"b/{header_path}",
            lineterm="",
        )
    )
    if not diff_lines:
        return None

    return "\n".join(diff_lines) + "\n"
