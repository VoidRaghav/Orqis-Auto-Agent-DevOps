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
    # Behavioural anomaly: a tool that normally returns structured data starts
    # returning an empty/degenerate payload and the agent consumes it without
    # validating. No exception — the corruption just propagates downstream.
    CORRUPT_TOOL_OUTPUT = "CORRUPT_TOOL_OUTPUT"
    # Behavioural anomaly: per-call token usage climbs far above the agent's own
    # baseline (unbounded memory / context not trimmed). No exception — the bill
    # just inflates, gradually, until someone notices.
    COST_SPIKE = "COST_SPIKE"
    # Behavioural anomaly: a tool is silently retried past a sane count because a
    # transient failure (timeout / 429 / 503) is retried with no backoff. The
    # call eventually succeeds, so nothing surfaces — it just bleeds time + money.
    RETRY_STORM = "RETRY_STORM"
    # Behavioural anomaly: a tool was bound/expected but the chain returned a
    # structured answer without ever invoking it (the LangChain bind + structured
    # output drop). Valid-looking JSON, but the tool's work never happened.
    TOOL_BINDING_DROP = "TOOL_BINDING_DROP"
    # Behavioural anomaly: two agents hand a task back and forth (A->B->A->B)
    # with no resolver or turn limit. Neither is looping alone — the orchestration
    # is — so it reads as normal per-agent activity while cost bleeds.
    MULTI_AGENT_PINGPONG = "MULTI_AGENT_PINGPONG"
    # Behavioural anomaly: per-call input tokens sit at/over the model's context
    # window, so the API silently truncates the context (often the system
    # instructions) and the agent answers off-policy. No error, just clipped input.
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    # Security anomaly: a user input carried an injection ("ignore previous
    # instructions...") and the agent obeyed — calling a tool outside its
    # established, allowed set. Behaviour diverged; no error was raised.
    PROMPT_INJECTION = "PROMPT_INJECTION"
    # Behavioural anomaly: an operation started and then went silent — the agent
    # is stuck waiting on something that never resolves. No error, no output,
    # just no progress. Only the absence of events reveals it.
    AGENT_STUCK = "AGENT_STUCK"
    # Behavioural anomaly: the model invoked a tool that isn't in the registered
    # set — it hallucinated a tool that doesn't exist. Sometimes throws, often
    # fails silently; either way the tool's work never happened.
    HALLUCINATED_TOOL = "HALLUCINATED_TOOL"
    # Behavioural anomaly: the agent invoked a destructive/write tool for a
    # read-only request (asked to "check", it "sent"/"deleted"). No error, just
    # the wrong — and often harmful — action.
    WRONG_TOOL = "WRONG_TOOL"
    # Behavioural anomaly: one agent produced a degenerate output that a
    # downstream agent consumed and passed on — a bad result poisoning the whole
    # pipeline. Each agent looks fine alone; only the chain fails.
    CASCADE_FAILURE = "CASCADE_FAILURE"
    # Catch-all: a run deviated sharply from this source's own established
    # baseline (calls, tokens, or cost) in a way no specific detector named. A
    # symptom of *some* failure — including new, unknown ones.
    ANOMALY = "ANOMALY"
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


class HeartbeatRequest(BaseModel):
    """Liveness ping from the SDK: the agent is up and running."""
    source: str = "sdk"


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
    # The tool's returned payload (JSON string) when the SDK captures it. Lets
    # the corruption detector spot an empty/degenerate result the agent consumed
    # without ever raising an exception.
    tool_result: Optional[str] = None
    # Structured-output / tool-binding integrity. bound_tools lists the tools the
    # SDK bound for this call; tool_invoked says whether one actually ran this
    # turn; structured_output flags a call that returned a structured object.
    # Together they catch a bound tool the chain silently never invoked.
    bound_tools: Optional[list[str]] = None
    tool_invoked: Optional[bool] = None
    structured_output: Optional[bool] = None
    # Multi-agent hand-off edge: which agent passed the task to which. Lets the
    # ping-pong detector see the A<->B alternation the loop detector is blind to.
    handoff_from: Optional[str] = None
    handoff_to: Optional[str] = None
    # The user/prompt text that drove this call, when captured. Lets the injection
    # detector correlate an out-of-policy tool call with an injection in the input.
    input_text: Optional[str] = None
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
    PATCHING        = "patching"         # LLM patch generation in flight
    PATCHED         = "patched"          # diff validated, awaiting approval
    LOW_CONFIDENCE  = "low_confidence"   # diff generated but failed verification
    APPROVED        = "approved"         # patch applied to disk (local dev path)
    DISMISSED       = "dismissed"        # human dismissed — no action taken
    # --- GitHub PR-first lifecycle ---
    PR_OPEN         = "pr_open"          # fix PR opened on GitHub, awaiting merge
    PR_FAILED       = "pr_failed"        # PR creation failed (retryable)
    PATCH_STALE     = "patch_stale"      # diff no longer applies to default-branch HEAD
    RESOLVED        = "resolved"         # PR merged — fix is in, awaiting deploy


class ValidationStatus(str, Enum):
    PENDING        = "pending"
    PASSED         = "passed"
    FAILED         = "failed"
    LOW_CONFIDENCE = "low_confidence"


class ChangeLogEntry(BaseModel):
    """
    An auditable record of something Orqis changed — written to the dashboard
    "CHANGES" feed and (for local applies) reflecting an actual file edit.

    One entry is created whenever a fix is applied locally, a fix PR is opened,
    a PR is merged/resolved, or an incident is dismissed.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    # "fix_applied" | "pr_opened" | "pr_merged" | "resolved" | "dismissed"
    # | "pr_failed" | "patch_stale"
    action: str
    incident_id: str
    summary: str                              # human-readable one-liner
    file: Optional[str] = None                # path that changed (relative when known)
    # True when the change was written to the local working copy on disk.
    applied_locally: bool = False
    local_path: Optional[str] = None          # absolute path edited on disk
    repo_full_name: Optional[str] = None
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    error_type: Optional[ErrorType] = None
    diff: Optional[str] = None


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

    # --- GitHub PR-first integration fields ---
    # How the patch was produced: "deterministic" (libcst remediation, correct by
    # construction) or "llm" (model rewrite). Auto-merge is gated on this.
    fix_method: Optional[str] = None
    # Scope of the fix, which sets the trust tier:
    #   "guard"      — a small, local, verified change (auto-merge safe)
    #   "structural" — an LLM rewrite, or a systemic pattern seen at >1 site
    #                  (needs a human to review; never auto-merged)
    fix_scope: Optional[str] = None
    # Repo-relative path of the file the fix touches (e.g. "demo/service.py"),
    # distinct from file_path which may be a deploy-absolute path like /app/demo/service.py.
    repo_relative_path: Optional[str] = None
    # Target repo + base branch the PR is opened against.
    repo_full_name: Optional[str] = None      # "owner/repo"
    base_branch: Optional[str] = None
    base_sha: Optional[str] = None
    # PR metadata once opened.
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_error: Optional[str] = None            # reason PR creation/staleness failed
    # Money recovered by stopping a runaway loop — shown in the PR title.
    cost_recovered_usd: Optional[float] = None
    # Set when the PR merges.
    resolved_at: Optional[datetime] = None