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
    type: str  # "log.event" | "log.interpretation"
    data: dict