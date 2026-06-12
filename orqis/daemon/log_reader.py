"""
Log stream ingestion and processing pipeline.

Supports two input modes:
  - stdin:    pipe server logs directly into the daemon (tail -f | python -m orqis)
  - file:     daemon tails a file path on disk (e.g. /var/log/app.log)

Processing flow per line:
  1. Classify synchronously with pattern_matcher (~0.1ms)
  2. POST the LogEvent to the backend immediately (dashboard shows the line)
  3. If error: fire async LLM interpretation concurrently
  4. When interpretation resolves: PATCH backend with the plain-English text
  5. Multi-line tracebacks are buffered; when the exception line arrives the
     full traceback is POSTed to /rca/trigger so the RCA pipeline can locate
     the failing code and generate a patch.
"""

import asyncio
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx

from .. import config
from ..backend.models import InterpretationUpdate, LogEvent, LogLevel
from ..daemon import interpreter, pattern_matcher

# Per-source traceback accumulator: source -> list of lines
# Cleared when the terminal exception line arrives or on a non-traceback line.
_tb_buffers: dict[str, list[str]] = defaultdict(list)

# A line that starts a Python traceback
_TB_START = re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)
# A line that is a stack frame inside a traceback (indented with "File ")
_TB_FRAME = re.compile(r'^\s+File "')
# A line that ends the traceback — the exception class and message
_TB_END = re.compile(r"^[A-Za-z][\w.]*Error[:\s]|^[A-Za-z][\w.]*Exception[:\s]")


async def _post_event(client: httpx.AsyncClient, event: LogEvent) -> None:
    """Send the classified log event to the backend."""
    try:
        await client.post(
            f"{config.BACKEND_URL}/events",
            json=event.model_dump(mode="json"),
            timeout=5.0,
        )
    except Exception as e:
        print(f"[orqis] backend unreachable — running in console-only mode ({type(e).__name__})", file=sys.stderr)


async def _post_interpretation(
    client: httpx.AsyncClient, event_id: str, text: str
) -> None:
    """Send the LLM interpretation update to the backend."""
    update = InterpretationUpdate(event_id=event_id, interpretation=text)
    try:
        await client.patch(
            f"{config.BACKEND_URL}/events/{event_id}/interpretation",
            json=update.model_dump(),
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        print(f"[orqis] failed to post interpretation: {e}", file=sys.stderr)


async def process_line(
    client: httpx.AsyncClient,
    line: str,
    source: str = "unknown",
) -> None:
    """
    Process a single log line end-to-end.

    Non-errors are posted and forgotten immediately.
    Errors trigger a background interpretation task.
    """
    line = line.rstrip("\n")
    if not line:
        return

    level, is_error, error_type, parsed_source, _ = pattern_matcher.classify(line)

    # For errors: set the static fallback immediately so the event always
    # has a readable interpretation from the first instant it appears.
    # The async LLM call will replace it with a better sentence when it resolves.
    initial_interpretation = interpreter.fallback(error_type) if is_error else None

    event = LogEvent(
        timestamp=datetime.now(timezone.utc),
        raw_line=line,
        level=level,
        is_error=is_error,
        error_type=error_type,
        source=parsed_source or source,
        interpretation=initial_interpretation,
    )

    # Print every line to console so the user can see the stream
    _print_event(event)

    # Fire-and-forget: post the event now, already has fallback interpretation
    await _post_event(client, event)

    if is_error:
        # Async LLM call — replaces the fallback with a contextual sentence
        asyncio.create_task(
            _interpret_and_update(client, event.id, line, error_type)
        )

    # Traceback buffering for RCA pipeline
    _handle_traceback(client, line, event.source)


def _print_event(event: LogEvent) -> None:
    """Print a classified log event to stdout with colour codes."""
    level_colours = {
        LogLevel.DEBUG:    "\033[90m",   # dark grey
        LogLevel.INFO:     "\033[0m",    # default
        LogLevel.WARNING:  "\033[33m",   # yellow
        LogLevel.ERROR:    "\033[31m",   # red
        LogLevel.CRITICAL: "\033[1;31m", # bold red
    }
    reset = "\033[0m"
    colour = level_colours.get(event.level, reset)

    tag = f"[{event.error_type.value}]" if event.error_type else ""
    ts = event.timestamp.strftime("%H:%M:%S")
    print(f"{colour}{ts}  {event.level.value:<8}  {tag:<16}  {event.raw_line}{reset}")


# A traceback that never terminates is discarded past this many lines.
_MAX_TB_LINES = 200


def _handle_traceback(client: httpx.AsyncClient, line: str, source: str) -> None:
    """
    Buffer traceback lines per source. When the terminal exception line
    arrives, flush the full traceback to the RCA pipeline trigger endpoint.

    A Python traceback body alternates between "File ..." frame lines and
    indented source-code lines, so both — plus blank lines — must be kept.
    Only a non-indented line that is not the exception terminator ends it.
    """
    buf = _tb_buffers[source]

    if _TB_START.search(line):
        _tb_buffers[source] = [line]
        return

    if not buf:
        return

    stripped = line.strip()

    # Terminal exception line — flush the full traceback to RCA
    if _TB_END.match(stripped):
        buf.append(line)
        full_tb = "\n".join(buf)
        _tb_buffers[source] = []
        asyncio.create_task(_post_rca_trigger(client, full_tb, source))
        return

    # Frame lines, indented source-code lines and blank lines are body
    if _TB_FRAME.match(line) or line[:1] in (" ", "\t") or not stripped:
        buf.append(line)
        if len(buf) > _MAX_TB_LINES:
            _tb_buffers[source] = []
        return

    # Non-indented, non-terminator line — traceback ended unrecognized
    _tb_buffers[source] = []


async def _post_rca_trigger(
    client: httpx.AsyncClient, traceback_text: str, source: str
) -> None:
    """POST a full traceback to the backend RCA trigger endpoint."""
    lines = len(traceback_text.splitlines())
    try:
        resp = await client.post(
            f"{config.BACKEND_URL}/rca/trigger",
            json={"traceback": traceback_text, "source": source},
            timeout=10.0,
        )
        print(
            f"\033[35m[orqis] RCA triggered — {lines}-line traceback "
            f"→ {resp.status_code}\033[0m",
            file=sys.stderr,
        )
    except Exception as e:
        print(
            f"\033[31m[orqis] RCA trigger failed ({type(e).__name__}): {e}\033[0m",
            file=sys.stderr,
        )


async def _interpret_and_update(client, event_id, line, error_type) -> None:
    text = await interpreter.interpret(line, error_type)
    # Show which error this interpretation belongs to (first 60 chars)
    label = line.strip()[:60] + ("..." if len(line.strip()) > 60 else "")
    print(f"\033[36m            => [{label}]\033[0m")
    print(f"\033[36m               {text}\033[0m")
    await _post_interpretation(client, event_id, text)


# --- Stream readers -----------------------------------------------------------

async def read_stdin(source: str = "stdin") -> None:
    """Read log lines from stdin indefinitely."""
    async with httpx.AsyncClient() as client:
        loop = asyncio.get_running_loop()
        while True:
            # Read stdin in a thread to avoid blocking the event loop
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                # EOF — wait for any in-flight interpretation tasks to finish
                pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                break
            await process_line(client, line, source=source)


async def tail_file(path: str, source: Optional[str] = None) -> None:
    """
    Tail a log file, processing new lines as they are appended.
    Starts from the end of the file (like tail -f, not tail -F).
    """
    source = source or path
    async with httpx.AsyncClient() as client:
        with open(path, "r") as f:
            # Seek to end — only process new lines from this point
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    await process_line(client, line, source=source)
                else:
                    # No new data — sleep briefly and poll again
                    await asyncio.sleep(0.05)


async def ingest_lines(
    lines: list[str],
    source: str = "api",
) -> list[LogEvent]:
    """
    Process a batch of log lines submitted via the HTTP /ingest endpoint.

    Returns the list of LogEvent objects so the backend can immediately store
    and broadcast them without waiting for a second round-trip.

    Each error line gets its own short-lived httpx client so background
    interpretation tasks are not racing against a shared client being closed.
    """
    events: list[LogEvent] = []
    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue

        level, is_error, error_type, parsed_source, _ = pattern_matcher.classify(line)
        event = LogEvent(
            timestamp=datetime.now(timezone.utc),
            raw_line=line,
            level=level,
            is_error=is_error,
            error_type=error_type,
            source=parsed_source or source,
            interpretation=interpreter.fallback(error_type) if is_error else None,
        )
        events.append(event)

        if is_error:
            asyncio.create_task(_interpret_and_update_standalone(event.id, line, error_type))

    return events


async def _interpret_and_update_standalone(event_id: str, line: str, error_type) -> None:
    """Interpretation task with its own client — safe to run after ingest returns."""
    async with httpx.AsyncClient() as client:
        await _interpret_and_update(client, event_id, line, error_type)