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

import asyncio
import difflib
import re
from typing import Optional

import httpx

from .. import config, llm
from ..daemon.interpreter import _warn_llm
from ..rca.file_reader import CodeLocation

# A fix is worth more than a few extra calls: if the whole provider chain comes
# back empty (a simultaneous transient outage), retry before giving up so a blip
# never leaves an incident unfixed.
_MAX_PATCH_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 2.0

# Below this size we include the WHOLE file as read-only reference alongside the
# block to fix, so the model uses real names/definitions (no inventing) and can
# add a nested helper — while still returning only the small block (fast, safe).
_MAX_REFERENCE_LINES = 500

# Output budget for a single-block rewrite. Small and fast; no truncation risk.
_BLOCK_MAX_TOKENS = 8192

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

# Corruption fixes are also structural: the code runs fine, but it uses a tool's
# return value without checking it, so an empty/degenerate payload silently
# propagates. Steer the model toward a validation guard right after the tool call.
_CORRUPTION_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below runs without error but consumes a tool's return value \
without validating it, so an empty or degenerate payload propagates corrupt \
data downstream. Return the COMPLETE corrected version of that same block with \
a validation guard added. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Right after the tool call, check its result is present and well-formed; if it \
is empty or missing expected fields, stop and fail loudly (raise) or return a \
safe fallback instead of using the bad value.
- Keep the normal-case behaviour unchanged — only add the guard.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Cost-spike fixes are structural too: the code runs fine, but its memory grows
# unbounded so per-call tokens climb. Steer the model toward trimming history.
_COST_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below runs without error but its per-call token usage climbs \
because it appends to its memory/context every turn and never trims it. Return \
the COMPLETE corrected version of that same block that bounds the memory. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Keep only the most recent N turns of history (a sensible cap like 20); trim in \
place so the change is local and the normal-case behaviour is unchanged.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Retry-storm fixes are structural too: a transient failure is retried in a
# tight loop with no backoff. Steer the model toward exponential backoff.
_RETRY_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below runs without error but retries a transient failure in a \
tight loop with no backoff, hammering a struggling downstream and bleeding cost. \
Return the COMPLETE corrected version of that same block with backoff added. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Add exponential backoff between attempts (e.g. time.sleep(min(2 ** attempt, 8))), \
capped so it never sleeps too long. Keep the normal-case behaviour unchanged.
- If you use time.sleep, make sure `import time` is present.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Tool-binding drop is a framework bug, not a code typo: chaining bind_tools with
# with_structured_output drops the tool, so the tool is never invoked. Steer the
# model toward the documented fix that keeps the tool call intact.
_BINDING_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below binds a tool AND requests structured output on the same \
chain (e.g. .bind_tools([...]).with_structured_output(...)). This is the known \
LangChain bug where the tool binding is silently dropped, so the tool is never \
invoked and the model fabricates the structured object. Return the COMPLETE \
corrected version of that same block that keeps the tool actually being called. \
Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Restructure so the tool is genuinely invoked and its result drives the output \
(e.g. bind the tools, invoke, then parse — do not chain with_structured_output \
on top of bind_tools). Keep the function's inputs and return shape the same.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Context-overflow fixes bound a prompt that exceeds the model's window. Steer
# the model toward keeping only what fits (a slice, or relevance-ranked retrieval).
_CONTEXT_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below builds a prompt larger than the model's context window, so \
the API silently truncates it. Return the COMPLETE corrected version of that same \
block that bounds the context so it fits. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Keep only what fits the window — slice the collection to the most relevant / \
most recent items (a sensible cap), rather than stuffing everything in.
- Do not call functions that don't already exist in the block.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Prompt-injection fixes add a guardrail: an injection pushed the agent into a
# tool outside its allowed set. Steer the model toward enforcing an allowlist.
_INJECTION_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below let a prompt injection push the agent into calling a tool \
outside its allowed set. Return the COMPLETE corrected version that stops this. \
Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Before executing the chosen tool, enforce an allowlist: check the tool is one \
the agent is permitted to use and refuse otherwise (raise or return a safe \
message). If the block already defines an allowed-tools set, use it.
- Do not call functions or names that don't already exist in the block.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Stuck-agent fixes bound an unbounded wait: the code waits on something that
# never resolves. Steer the model toward a timeout / maximum-attempts limit.
_TIMEOUT_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below can hang forever: it waits on an operation that may never \
resolve, with no timeout or attempt limit. Return the COMPLETE corrected version \
that cannot hang. Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Add a bound: a maximum number of attempts or a deadline; when it is reached, \
stop waiting and return a safe value or raise a clear timeout — do not hang.
- Do not call functions or names that don't already exist in the block.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

# Hallucinated-tool fixes need a real resolution step, not a one-line guard: the
# model named a tool that doesn't exist, and the code ran it unchecked. Steer the
# model toward validating the tool against the registry before dispatch.
_HALLUCINATION_SYSTEM_PROMPT = """\
You are Orqis, a production incident auto-patcher.

The code block below dispatched a tool the model chose without checking it exists \
in the agent's registered tool set, so a hallucinated (nonexistent) tool ran and \
did nothing. Return the COMPLETE corrected version that resolves this properly. \
Rules:
- Output ONLY the corrected code — no explanation, no markdown fences, no diff.
- Return the entire block you were given, start to end.
- Add a real tool-resolution step: before dispatch, verify the chosen tool is in \
the known/registered set; if it isn't, do not run it — return a clear "unknown \
tool" result or raise. Prefer a small helper function if it makes the block clean.
- Use the registry the block already defines; don't invent new globals.
- Preserve every other line exactly, including indentation and blank lines.
- If you cannot produce a safe fix, output exactly: NO_FIX
"""

_SYSTEM_PROMPTS = {
    "loop": _LOOP_SYSTEM_PROMPT,
    "corruption": _CORRUPTION_SYSTEM_PROMPT,
    "cost": _COST_SYSTEM_PROMPT,
    "retry": _RETRY_SYSTEM_PROMPT,
    "binding": _BINDING_SYSTEM_PROMPT,
    "context": _CONTEXT_SYSTEM_PROMPT,
    "injection": _INJECTION_SYSTEM_PROMPT,
    "timeout": _TIMEOUT_SYSTEM_PROMPT,
    "hallucination": _HALLUCINATION_SYSTEM_PROMPT,
}


async def generate(
    error_message: str,
    location: CodeLocation,
    kind: str = "error",
) -> Optional[str]:
    """
    Generate a unified diff for the given error and code location.

    kind="error" fixes a raised exception; kind="loop" adds a bounded-retry
    guard to a no-exit-condition agent loop; kind="corruption" adds a validation
    guard for an unchecked tool result. Returns the diff string, or None if no
    safe fix could be produced. Never raises — any failure returns None.
    """
    system = _SYSTEM_PROMPTS.get(kind, _SYSTEM_PROMPT)
    prompt = _build_prompt(error_message, location)

    # Retry the chain a few times: a fix is worth far more than the extra calls,
    # and a transient outage must not leave the incident unpatched. Each attempt
    # already cascades Gemini -> Groq -> ... so one attempt survives an outage.
    for attempt in range(_MAX_PATCH_ATTEMPTS):
        raw = await _generate_raw(prompt, system, _BLOCK_MAX_TOKENS)
        if raw is not None:
            diff = _diff_from_rewrite(raw, location)
            if diff is not None:
                return diff
        if attempt + 1 < _MAX_PATCH_ATTEMPTS:
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
    return None


async def _generate_raw(prompt: str, system: str, max_tokens: int = _BLOCK_MAX_TOKENS) -> Optional[str]:
    """
    Try each configured LLM provider in order until one returns a patch, so a
    single provider's outage — a free-tier 503, a rate limit, a dead key — never
    blocks a fix. Order: Gemini (free, strong) -> Groq (free, instant) -> OpenAI
    (paid, last resort) -> Anthropic (if set) -> local Ollama.
    """
    if config.GEMINI_API_KEY:
        raw = await llm.generate(prompt, system, config.GEMINI_PATCH_MODEL, max_tokens=max_tokens)
        if raw:
            return raw
    if config.GROQ_API_KEY:
        raw = await llm.openai_chat(
            prompt, system, config.GROQ_BASE_URL, config.GROQ_API_KEY,
            config.GROQ_PATCH_MODEL, provider="Groq", max_tokens=max_tokens,
        )
        if raw:
            return raw
    if config.OPENAI_API_KEY:
        raw = await llm.openai_chat(
            prompt, system, config.OPENAI_BASE_URL, config.OPENAI_API_KEY,
            config.OPENAI_PATCH_MODEL, provider="OpenAI", max_tokens=max_tokens,
        )
        if raw:
            return raw
    if config.ANTHROPIC_API_KEY:
        raw = await _call_anthropic(prompt, system, max_tokens)
        if raw:
            return raw
    return await _call_ollama(prompt, system, max_tokens)


def _build_prompt(error_message: str, location: CodeLocation) -> str:
    func_label = f"function `{location.function_name}`" if location.function_name else "module-level code"

    # Include the full file as read-only reference when it's small, so the model
    # uses the real names/definitions (registries, helpers) instead of inventing
    # them — while still only rewriting the small block below.
    reference = ""
    src = location.source_text
    if src and src != location.context and len(src.splitlines()) <= _MAX_REFERENCE_LINES:
        reference = (
            "Full file for reference — use its existing names and definitions, do "
            "NOT invent new module-level names. If the fix needs a helper, define "
            "it inside the block (a nested function):\n"
            f"```python\n{src}\n```\n\n"
        )

    return (
        f"Error:\n{error_message}\n\n"
        f"File: {location.file_path}\n"
        f"Error at line: {location.line}\n"
        f"{reference}"
        f"Code block to repair ({func_label}, lines "
        f"{location.context_start_line}-{location.context_start_line + len(location.context.splitlines()) - 1}):\n"
        f"```python\n{location.context}\n```\n\n"
        f"Return ONLY the complete corrected version of that block."
    )


async def _call_ollama(prompt: str, system: str, max_tokens: int = _BLOCK_MAX_TOKENS) -> Optional[str]:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens},
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


async def _call_anthropic(prompt: str, system: str, max_tokens: int = _BLOCK_MAX_TOKENS) -> Optional[str]:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model=config.ANTHROPIC_PATCH_MODEL,
            max_tokens=max_tokens,
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
