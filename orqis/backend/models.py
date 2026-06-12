import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorType(str, Enum):
    RECURSION = "RECURSION"
    MEMORY = "MEMORY"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    AUTHENTICATION = "AUTHENTICATION"
    HTTP_ERROR = "HTTP_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    VALUE_ERROR = "VALUE_ERROR"
    ATTRIBUTE_ERROR = "ATTRIBUTE_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    TRACEBACK = "TRACEBACK"
    RATE_LIMIT = "RATE_LIMIT"
    TOOL_FAILURE = "TOOL_FAILURE"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    # Behavioural anomaly: an agent calling the same tool with no exit condition.
    # No exception is ever raised — only the live trace stream reveals it.
    RUNAWAY_LOOP = "RUNAWAY_LOOP"
    GENERIC = "GENERIC"


class LogEvent(BaseModel):
    # Unique ID used to match async interpretation updates back to this event
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    raw_line: str
    level: LogLevel
    is_error: bool
    error_type: Optional[ErrorType] = None
    source: str = "unknown"
    # Filled in ~500ms later via async LLM call (None until then)
    interpretation: Optional[str] = None


class IngestRequest(BaseModel):
    """HTTP payload when a server POSTs raw log lines to /ingest."""
    lines: list[str]
    source: str = "unknown"


class InterpretationUpdate(BaseModel):
    """Sent from daemon to backend when the LLM interpretation is ready."""
    event_id: str
    interpretation: str


class WsMessage(BaseModel):
    """Envelope for all WebSocket messages sent to the dashboard."""
    type: str  # "log.event" | "log.interpretation" | "trace.event"
    data: dict


class EventKind(str, Enum):
    LLM_START   = "llm.start"
    LLM_END     = "llm.end"
    LLM_ERROR   = "llm.error"
    TOOL_START  = "tool.start"
    TOOL_END    = "tool.end"
    TOOL_ERROR  = "tool.error"
    CHAIN_START = "chain.start"
    CHAIN_END   = "chain.end"
    CHAIN_ERROR = "chain.error"


class TraceEvent(BaseModel):
    """
    Rich structured event emitted by the SDK instrumentation layer.
    One TraceEvent per LLM call / tool call / chain step.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    kind: EventKind
    provider: str           # "openai" | "anthropic" | "langchain"
    run_id: str             # groups start/end pairs and related events
    model: Optional[str] = None
    # Tool-call identity — used by the runaway-loop detector to spot an agent
    # invoking the same tool with the same arguments over and over.
    tool_name: Optional[str] = None
    tool_args: Optional[str] = None
    # Where this call originates in the agent's source, "file.py:line:function".
    # Lets the RCA pipeline locate the loop without a traceback.
    code_location: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    is_error: bool = False
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    interpretation: Optional[str] = None  # filled async when is_error=True
    source: str = "sdk"


class IncidentStatus(str, Enum):
    OPEN            = "open"             # detected, patch not yet generated
    PATCHED         = "patched"          # diff validated, awaiting approval
    LOW_CONFIDENCE  = "low_confidence"   # diff generated but failed verification
    APPROVED        = "approved"         # patch applied to disk
    DISMISSED       = "dismissed"        # human dismissed — no action taken


class ValidationStatus(str, Enum):
    PENDING        = "pending"
    PASSED         = "passed"
    FAILED         = "failed"
    LOW_CONFIDENCE = "low_confidence"


class Incident(BaseModel):
    """
    A grouped error event with an optional generated patch.
    Created whenever a log or trace error has a traceback with a resolvable file.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime
    status: IncidentStatus = IncidentStatus.OPEN

    # Source event that triggered this incident
    source_event_id: str
    error_type: Optional[ErrorType] = None
    error_message: str
    interpretation: Optional[str] = None

    # Code location resolved from the traceback
    file_path: Optional[str] = None
    error_line: Optional[int] = None
    function_name: Optional[str] = None
    # The code context snippet shown alongside the diff
    code_context: Optional[str] = None
    context_start_line: Optional[int] = None

    # Unified diff string produced by the patch generator
    diff: Optional[str] = None

    # Verification pipeline results
    validation_status:   ValidationStatus = ValidationStatus.PENDING
    confidence:          Optional[int] = None        # 0-100
    validation_errors:   list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)

    source: str = "unknown"
    # How many times this exact error has fired (dedup counter)
    hit_count: int = 1