export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type ErrorType =
  | "RECURSION" | "MEMORY" | "TIMEOUT" | "CONNECTION" | "AUTHENTICATION"
  | "HTTP_ERROR" | "TYPE_ERROR" | "VALUE_ERROR" | "ATTRIBUTE_ERROR"
  | "IMPORT_ERROR" | "TRACEBACK" | "RATE_LIMIT" | "TOOL_FAILURE"
  | "SYNTAX_ERROR" | "PERMISSION_ERROR" | "RUNAWAY_LOOP" | "GENERIC";

export type IncidentStatus =
  | "open" | "patching" | "patched" | "low_confidence" | "approved" | "dismissed"
  | "pr_open" | "pr_failed" | "patch_stale" | "resolved";

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
  tool_args: string | null;
  code_location: string | null;
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
  // GitHub PR-first fields
  fix_method: "deterministic" | "llm" | null;
  repo_relative_path: string | null;
  repo_full_name: string | null;
  base_branch: string | null;
  base_sha: string | null;
  branch_name: string | null;
  pr_number: number | null;
  pr_url: string | null;
  pr_error: string | null;
  cost_recovered_usd: number | null;
  resolved_at: string | null;
}

export interface WorkspaceSettings {
  installation_id: number | null;
  account_login: string | null;
  repos: string[];
  source_repo_map: Record<string, string>;
  default_repo: string;
  default_branch: string;
  hot_reload_webhook_url: string;
  auto_merge_enabled: boolean;
  pr_low_confidence: boolean;
}

export interface GithubConnectInfo {
  configured: boolean;
  install_url: string;
  connected: boolean;
  account_login: string | null;
  repos: string[];
}

export interface IdeSetupInfo {
  backend_url: string;
  mcp_command: string;
  note: string;
  configs: Record<string, unknown>;
  ides: { name: string; config: string }[];
}

export type ChangeAction =
  | "fix_applied" | "pr_opened" | "pr_merged" | "resolved" | "dismissed"
  | "pr_failed" | "patch_stale";

export interface ChangeLogEntry {
  id: string;
  timestamp: string;
  action: ChangeAction;
  incident_id: string;
  summary: string;
  file: string | null;
  applied_locally: boolean;
  local_path: string | null;
  repo_full_name: string | null;
  pr_url: string | null;
  pr_number: number | null;
  error_type: ErrorType | null;
  diff: string | null;
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
  | { type: "incident.pr_opened";     data: Incident }
  | { type: "incident.resolved";      data: Incident }
  | { type: "incident.interpretation";data: Incident }
  | { type: "change.logged";          data: ChangeLogEntry }
  | { type: "settings.updated";       data: GithubConnectInfo }
  | { type: "store.cleared";          data: Record<string, never> };
