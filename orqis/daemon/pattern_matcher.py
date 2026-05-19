"""
Rule-based log line classifier.

Two-pass approach:
  1. Parse the line to extract level, source, and message from common log formats.
  2. Classify the error type using regex patterns against the full raw line.

This runs synchronously and completes in ~0.1ms — no I/O, no LLM.
"""

import json
import re
from typing import Optional, Tuple

from ..backend.models import ErrorType, LogLevel


# --- Log format parsers -------------------------------------------------------

# Matches: 2024-01-01 14:31:02,123 ERROR module.name - Message
# Matches: 2024-01-01 14:31:02 ERROR module.name: Message
_STANDARD_LOG = re.compile(
    r"(?P<ts>[\d\-T:,.Z+]+)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s+"
    r"(?P<source>\S+)[\s\-:]+(?P<message>.+)",
    re.IGNORECASE,
)

# Matches: [14:31:02] ERROR  source.name   Message
_BRACKETED_LOG = re.compile(
    r"\[[\d:T\-\s]+\]\s+"
    r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s+"
    r"(?P<source>\S+)\s+(?P<message>.+)",
    re.IGNORECASE,
)

# Matches: level=ERROR ts=... msg="..."  (logfmt style)
_LOGFMT = re.compile(
    r'level=(?P<level>\w+).*?(?:msg|message)=["\']?(?P<message>[^"\']+)',
    re.IGNORECASE,
)


def _parse_line(line: str) -> Tuple[Optional[LogLevel], Optional[str], Optional[str]]:
    """
    Try to extract (level, source, message) from a log line.
    Returns (None, None, None) if the format is not recognized.
    """
    stripped = line.strip()

    # JSON log lines (e.g. structured logging, Datadog agent, etc.)
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
            level_raw = (
                obj.get("level") or obj.get("severity") or obj.get("lvl") or ""
            )
            message = (
                obj.get("message") or obj.get("msg") or obj.get("error") or ""
            )
            source = obj.get("logger") or obj.get("name") or obj.get("service") or ""
            return _normalize_level(str(level_raw)), str(source), str(message)
        except (json.JSONDecodeError, TypeError):
            pass

    # logfmt style
    m = _LOGFMT.search(stripped)
    if m:
        return _normalize_level(m.group("level")), None, m.group("message")

    # Standard Python / ISO timestamp format
    m = _STANDARD_LOG.match(stripped)
    if m:
        return (
            _normalize_level(m.group("level")),
            m.group("source"),
            m.group("message"),
        )

    # Bracketed timestamp format (LangChain daemon logs, etc.)
    m = _BRACKETED_LOG.match(stripped)
    if m:
        return (
            _normalize_level(m.group("level")),
            m.group("source"),
            m.group("message"),
        )

    return None, None, None


def _normalize_level(raw: str) -> Optional[LogLevel]:
    mapping = {
        "debug": LogLevel.DEBUG,
        "info": LogLevel.INFO,
        "warn": LogLevel.WARNING,
        "warning": LogLevel.WARNING,
        "error": LogLevel.ERROR,
        "critical": LogLevel.CRITICAL,
        "fatal": LogLevel.CRITICAL,
    }
    return mapping.get(raw.lower().strip())


# --- Keyword-based fallback level detection -----------------------------------

# Ordered by priority — first match wins
_LEVEL_KEYWORDS = [
    (re.compile(r"\b(CRITICAL|FATAL)\b"), LogLevel.CRITICAL),
    (re.compile(r"\bERROR\b"), LogLevel.ERROR),
    (re.compile(r"\b(WARNING|WARN)\b"), LogLevel.WARNING),
    (re.compile(r"\bDEBUG\b"), LogLevel.DEBUG),
    (re.compile(r"\bINFO\b"), LogLevel.INFO),
]


def _keyword_level(line: str) -> LogLevel:
    for pattern, level in _LEVEL_KEYWORDS:
        if pattern.search(line):
            return level
    return LogLevel.INFO


# --- Error type classification -------------------------------------------------

# Ordered by specificity — more specific patterns come first
_ERROR_TYPE_PATTERNS: list[Tuple[re.Pattern, ErrorType]] = [
    # Recursion / infinite loops
    (
        re.compile(
            r"RecursionError|maximum recursion depth|"
            r"infinite.loop|recursion limit|stack overflow",
            re.IGNORECASE,
        ),
        ErrorType.RECURSION,
    ),
    # OOM / memory
    (
        re.compile(
            r"MemoryError|out.of.memory|\bOOM\b|"
            r"heap space|cannot allocate|memory exhausted",
            re.IGNORECASE,
        ),
        ErrorType.MEMORY,
    ),
    # Timeouts
    (
        re.compile(
            r"TimeoutError|ReadTimeout|ConnectTimeout|"
            r"timed.out|deadline.exceeded|\btimeout\b",
            re.IGNORECASE,
        ),
        ErrorType.TIMEOUT,
    ),
    # Connection failures
    (
        re.compile(
            r"ConnectionError|ConnectionRefused|ConnectionReset|"
            r"connection.refused|ECONNREFUSED|ECONNRESET|"
            r"connection.failed|no route to host|network.unreachable",
            re.IGNORECASE,
        ),
        ErrorType.CONNECTION,
    ),
    # Auth / permission failures
    (
        re.compile(
            r"AuthenticationError|Unauthorized|Forbidden|"
            r"invalid.api.key|API key|401|403|"
            r"authentication.failed|permission.denied",
            re.IGNORECASE,
        ),
        ErrorType.AUTHENTICATION,
    ),
    # HTTP 4xx/5xx
    (
        re.compile(
            r"HTTP [45]\d{2}|status[_\s]?code[=:\s][45]\d{2}|"
            r"[45]\d{2} (Bad Request|Not Found|Internal Server|Gateway|Service Unavailable)",
            re.IGNORECASE,
        ),
        ErrorType.HTTP_ERROR,
    ),
    # Rate limiting (LLM APIs)
    (
        re.compile(
            r"RateLimitError|rate.limit|quota.exceeded|"
            r"too.many.requests|429",
            re.IGNORECASE,
        ),
        ErrorType.RATE_LIMIT,
    ),
    # Tool failures (LangChain / agent specific)
    (
        re.compile(
            r"ToolException|tool.call.failed|tool.error|"
            r"tool.invocation.failed|action.failed",
            re.IGNORECASE,
        ),
        ErrorType.TOOL_FAILURE,
    ),
    # Python exception types
    (re.compile(r"\bTypeError\b"), ErrorType.TYPE_ERROR),
    (re.compile(r"\bValueError\b"), ErrorType.VALUE_ERROR),
    (re.compile(r"\bAttributeError\b"), ErrorType.ATTRIBUTE_ERROR),
    (re.compile(r"\b(ImportError|ModuleNotFoundError)\b"), ErrorType.IMPORT_ERROR),
    (re.compile(r"\bSyntaxError\b"), ErrorType.SYNTAX_ERROR),
    (re.compile(r"\bPermissionError\b"), ErrorType.PERMISSION_ERROR),
    # Traceback header (marks start of a Python exception block)
    (
        re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
        ErrorType.TRACEBACK,
    ),
    # Catch-all: any line that IS the exception class (ZeroDivisionError:, KeyError: ...)
    # This fires when the exception name has no specific pattern above.
    (
        re.compile(r"^[A-Za-z][\w.]*(?:Error|Exception|Warning)[\s:,]", re.MULTILINE),
        ErrorType.TRACEBACK,
    ),
]


def _classify_error_type(line: str) -> Optional[ErrorType]:
    for pattern, error_type in _ERROR_TYPE_PATTERNS:
        if pattern.search(line):
            return error_type
    return None


# --- Public API ---------------------------------------------------------------

def classify(
    line: str,
) -> Tuple[LogLevel, bool, Optional[ErrorType], Optional[str], Optional[str]]:
    """
    Classify a single log line.

    Returns:
        level       - LogLevel enum value
        is_error    - True if this line should be surfaced as an error
        error_type  - ErrorType enum value, or None
        source      - extracted source/logger name, or None
        message     - extracted log message, or None
    """
    parsed_level, source, message = _parse_line(line)

    # Fall back to keyword scan if format wasn't recognized
    level = parsed_level if parsed_level is not None else _keyword_level(line)

    is_error = level in (LogLevel.ERROR, LogLevel.CRITICAL)

    # Always run error type classification — exception lines like `ZeroDivisionError:`
    # have no ERROR keyword but must be promoted so they reach the RCA pipeline.
    error_type = _classify_error_type(line)

    if error_type is not None and not is_error:
        # Promote to ERROR if the content looks like an error regardless of log level
        is_error = True
        level = LogLevel.ERROR

    # Clear error_type for lines that are genuinely not errors
    if not is_error:
        error_type = None

    return level, is_error, error_type, source, message
