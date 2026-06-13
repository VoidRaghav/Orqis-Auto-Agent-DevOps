export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type ErrorType =
  | "RECURSION" | "MEMORY" | "TIMEOUT" | "CONNECTION" | "AUTHENTICATION"
  | "HTTP_ERROR" | "TYPE_ERROR" | "VALUE_ERROR" | "ATTRIBUTE_ERROR"
  | "IMPORT_ERROR" | "TRACEBACK" | "RATE_LIMIT" | "TOOL_FAILURE"
  | "SYNTAX_ERROR" | "PERMISSION_ERROR" | "GENERIC";

export type IncidentStatus =
  | "open" | "patched" | "low_confidence" | "approved" | "dismissed";

export type ValidationStatus =
  | "pending" | "passed" | "failed" | "low_confidence";

export interface LogEvent {
  id: string;
  timestamp: string;
  raw_line: string;
  level: LogLevel;
  is_error: boolean;
  error_type: ErrorType | null;
  source: string;
  interpretation: string | null;
}

export interface TraceEvent {
  id: string;
  timestamp: string;
  kind: string;
  provider: string;
  run_id: string;
  model: string | null;
  tool_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  latency_ms: number | null;
  is_error: boolean;
  error_type: ErrorType | null;
  error_message: string | null;
  interpretation: string | null;
  source: string;
}

export interface Incident {
  id: string;
  created_at: string;
  status: IncidentStatus;
  source_event_id: string;
  error_type: ErrorType | null;
  error_message: string;
  interpretation: string | null;
  file_path: string | null;
  error_line: number | null;
  function_name: string | null;
  code_context: string | null;
  context_start_line: number | null;
  diff: string | null;
  validation_status: ValidationStatus;
  confidence: number | null;
  validation_errors: string[];
  validation_warnings: string[];
  source: string;
  hit_count: number;
}

export type WsPayload =
  | { type: "log.event";              data: LogEvent }
  | { type: "log.interpretation";     data: { event_id: string; interpretation: string } }
  | { type: "trace.event";            data: TraceEvent }
  | { type: "trace.interpretation";   data: { event_id: string; interpretation: string } }
  | { type: "incident.created";       data: Incident }
  | { type: "incident.located";       data: Incident }
  | { type: "incident.patched";       data: Incident }
  | { type: "incident.updated";       data: Incident }
  | { type: "incident.approved";      data: Incident }
  | { type: "incident.dismissed";     data: Incident }
  | { type: "incident.interpretation";data: Incident }
  | { type: "store.cleared";          data: Record<string, never> };
