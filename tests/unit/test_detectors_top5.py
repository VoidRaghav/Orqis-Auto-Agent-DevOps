"""Top-5 detector Tier-A fixtures: observe() signals + deterministic remediations.

Council milestone #3 — runaway, corruption, retry_storm, cost_spike, overflow.
These stay LLM-free so CI can gate them without Anthropic/Ollama.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import pytest

pytestmark = pytest.mark.unit

from orqis.backend.models import ErrorType, EventKind, TraceEvent
from orqis.rca import anomaly, corruption, cost_spike, overflow, retry_storm
from orqis.rca.file_reader import CodeLocation
from orqis.rca.remediation import (
    BACKOFF_CAP_SECONDS,
    MAX_ATTEMPTS,
    MAX_CONTEXT_DOCS,
    MAX_HISTORY,
    add_backoff,
    cap_context_window,
    cap_unbounded_memory,
    guard_corrupt_output,
    guard_runaway_loop,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tool(
    *,
    source: str,
    tool: str,
    args: str = '{"order_id":"1042"}',
    kind: EventKind = EventKind.TOOL_START,
    result: Optional[str] = None,
    is_error: bool = False,
    error_type: Optional[ErrorType] = None,
    code_location: Optional[str] = "src/refund_agent.py:11:resolve_refund",
) -> TraceEvent:
    return TraceEvent(
        timestamp=_now(),
        kind=kind,
        provider="langchain",
        run_id="run-1",
        model="gpt-4o",
        tool_name=tool,
        tool_args=args,
        tool_result=result,
        is_error=is_error,
        error_type=error_type,
        cost_usd=0.01,
        code_location=code_location,
        source=source,
    )


def _llm(
    *,
    source: str,
    tokens: int,
    model: str = "gpt-4o",
    code_location: Optional[str] = "src/agent.py:10:run",
) -> TraceEvent:
    return TraceEvent(
        timestamp=_now(),
        kind=EventKind.LLM_END,
        provider="openai",
        run_id="run-llm",
        model=model,
        input_tokens=tokens,
        cost_usd=0.02,
        code_location=code_location,
        source=source,
    )


def _loc(source: str, fn: str = "resolve_refund") -> CodeLocation:
    return CodeLocation(
        file_path="src/refund_agent.py",
        line=10,
        function_name=fn,
        context="",
        context_start_line=1,
        source_text=source,
        repo_relative_path="src/refund_agent.py",
    )


@pytest.fixture(autouse=True)
def _reset_detectors():
    anomaly.reset()
    corruption.reset()
    retry_storm.reset()
    cost_spike.reset()
    overflow.reset()
    yield
    anomaly.reset()
    corruption.reset()
    retry_storm.reset()
    cost_spike.reset()
    overflow.reset()


def test_anomaly_observe_fires_after_threshold():
    async def _run():
        src = "det-runaway"
        tool = "check_order_status"
        sig = None
        for _ in range(8):
            sig = await anomaly.observe(_tool(source=src, tool=tool))
        assert sig is not None
        assert sig.tool_name == tool

    asyncio.run(_run())


def test_guard_runaway_remediation_fixture():
    source = (
        "def resolve_refund(order_id):\n"
        "    status = check_order_status(order_id)\n"
        '    while status == "processing":\n'
        "        status = check_order_status(order_id)\n"
        "    return status\n"
    )
    diff = guard_runaway_loop(_loc(source))
    assert diff is not None
    assert str(MAX_ATTEMPTS) in diff


def test_corruption_observe_fires_after_degenerate_burst():
    async def _run():
        src = "det-corrupt"
        tool = "check_order_status"
        for _ in range(2):
            assert (
                await corruption.observe(
                    _tool(
                        source=src,
                        tool=tool,
                        kind=EventKind.TOOL_END,
                        result='{"status":"ok"}',
                    )
                )
                is None
            )
        sig = None
        for _ in range(3):
            sig = await corruption.observe(
                _tool(source=src, tool=tool, kind=EventKind.TOOL_END, result="{}")
            )
        assert sig is not None
        assert "status" in sig.expected_keys

    asyncio.run(_run())


def test_guard_corrupt_output_remediation_fixture():
    source = (
        "def resolve_refund(order_id):\n"
        "    result = check_order_status(order_id)\n"
        "    return result\n"
    )
    diff = guard_corrupt_output(_loc(source), "check_order_status")
    assert diff is not None
    assert "ValueError" in diff
    assert "check_order_status" in diff


def test_retry_storm_observe_fires_after_silent_retries():
    async def _run():
        src = "det-retry"
        tool = "fetch_payment"
        args = '{"id":"1"}'
        sig = None
        for _ in range(3):
            sig = await retry_storm.observe(
                _tool(
                    source=src,
                    tool=tool,
                    args=args,
                    kind=EventKind.TOOL_ERROR,
                    is_error=True,
                    error_type=ErrorType.TIMEOUT,
                )
            )
        assert sig is not None
        assert sig.retry_count >= 3

    asyncio.run(_run())


def test_add_backoff_remediation_fixture():
    source = (
        "def fetch_with_retry(order_id):\n"
        "    for attempt in range(5):\n"
        "        status = check_order_status(order_id)\n"
        "        if status == 'ok':\n"
        "            return status\n"
        "    return 'failed'\n"
    )
    diff = add_backoff(_loc(source, fn="fetch_with_retry"))
    assert diff is not None
    assert "time.sleep" in diff
    assert str(BACKOFF_CAP_SECONDS) in diff


def test_cost_spike_observe_fires_on_sustained_climb():
    async def _run():
        src = "det-cost"
        for tokens in (100, 110, 90, 105):
            assert await cost_spike.observe(_llm(source=src, tokens=tokens)) is None
        sig = None
        for tokens in (400, 450, 500):
            sig = await cost_spike.observe(_llm(source=src, tokens=tokens))
        assert sig is not None
        assert sig.peak_tokens >= 400

    asyncio.run(_run())


def test_cap_unbounded_memory_remediation_fixture():
    source = (
        "def run(self, turn):\n"
        "    self.memory.append(turn)\n"
        "    return self.memory\n"
    )
    diff = cap_unbounded_memory(_loc(source, fn="run"))
    assert diff is not None
    assert str(MAX_HISTORY) in diff
    assert "memory" in diff


def test_overflow_observe_fires_near_window():
    async def _run():
        src = "det-overflow"
        over = 120_000
        sig = None
        for _ in range(3):
            sig = await overflow.observe(_llm(source=src, tokens=over, model="gpt-4o"))
        assert sig is not None
        assert sig.window == 128_000

    asyncio.run(_run())


def test_cap_context_window_remediation_fixture():
    source = (
        "def build_prompt(docs):\n"
        '    text = "\\n".join(docs)\n'
        "    return text\n"
    )
    diff = cap_context_window(_loc(source, fn="build_prompt"))
    assert diff is not None
    assert str(MAX_CONTEXT_DOCS) in diff
