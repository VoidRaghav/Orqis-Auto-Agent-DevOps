import { colors, statusColors } from "@/lib/tokens";

/** Dashboard palette — aligned with landing tokens */
export const C = {
  green: colors.green,
  amber: colors.amber,
  red: colors.red,
  blue: colors.github,
  github: colors.github,
  nebula1: colors.ivory,
  nebula2: colors.muted,
  white: colors.white,
  ivory: colors.ivory,
  dim: colors.dim,
  dimmer: colors.dimmer,
  muted: colors.muted,
  bg: colors.bg,
  bg2: colors.bg2,
  bg3: colors.bg3,
  border: colors.border,
  glow: colors.glow,
};

export const LEVEL_COLOR: Record<string, string> = {
  DEBUG: C.dim,
  INFO: C.muted,
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
  TYPE_ERROR: C.ivory,
  VALUE_ERROR: C.ivory,
  ATTRIBUTE_ERROR: C.ivory,
  IMPORT_ERROR: C.ivory,
  TOOL_FAILURE: C.amber,
  SYNTAX_ERROR: C.red,
  PERMISSION_ERROR: C.amber,
  GENERIC: C.dim,
  RUNAWAY_LOOP: C.amber,
};

export const ACTIVE_STATUSES = new Set<string>([
  "open",
  "patching",
  "patched",
  "low_confidence",
  "pr_open",
  "pr_failed",
  "patch_stale",
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

export function incidentStatusColor(status: string): string {
  return statusColors[status] ?? C.dim;
}
