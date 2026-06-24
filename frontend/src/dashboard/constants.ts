export const C = {
  green: "#00ff41",
  amber: "#ffb000",
  red: "#ff2a2a",
  blue: "#7dd3fc",
  github: "#7dd3fc",
  nebula1: "#ececec",
  nebula2: "#8a8a8a",
  white: "#ececec",
  dim: "#555555",
  dimmer: "#333333",
  bg: "#050505",
  bg2: "#0c0c0c",
  bg3: "#111111",
  border: "rgba(255,255,255,0.08)",
};

export const LEVEL_COLOR: Record<string, string> = {
  DEBUG: C.dim,
  INFO: "#8a8a8a",
  WARNING: C.amber,
  ERROR: C.red,
  CRITICAL: C.red,
};

export const TYPE_COLOR: Record<string, string> = {
  CONNECTION: C.blue,
  AUTHENTICATION: C.amber,
  RATE_LIMIT: C.amber,
  TIMEOUT: C.amber,
  MEMORY: C.red,
  RECURSION: C.red,
  HTTP_ERROR: C.red,
  TRACEBACK: C.red,
  TYPE_ERROR: C.white,
  VALUE_ERROR: C.white,
  ATTRIBUTE_ERROR: C.white,
  IMPORT_ERROR: C.white,
  TOOL_FAILURE: C.amber,
  SYNTAX_ERROR: C.red,
  PERMISSION_ERROR: C.amber,
  GENERIC: C.dim,
  RUNAWAY_LOOP: C.amber,
};

export const ACTIVE_STATUSES = new Set<string>([
  "open", "patching", "patched", "low_confidence", "pr_open", "pr_failed", "patch_stale",
]);

export const HEALED_STATUSES = new Set<string>(["approved", "resolved"]);

export const CHANGE_META: Record<string, { label: string; color: string; icon: string }> = {
  fix_applied: { label: "APPLIED LOCALLY", color: C.green, icon: "✎" },
  pr_opened: { label: "PR OPENED", color: C.github, icon: "⤴" },
  pr_merged: { label: "PR MERGED", color: C.green, icon: "✓" },
  resolved: { label: "RESOLVED", color: C.green, icon: "✓" },
  dismissed: { label: "DISMISSED", color: C.dim, icon: "—" },
  pr_failed: { label: "PR FAILED", color: C.red, icon: "!" },
  patch_stale: { label: "PATCH STALE", color: C.amber, icon: "△" },
};
