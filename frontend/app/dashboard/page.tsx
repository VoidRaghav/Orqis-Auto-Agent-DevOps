"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useOrqisStream } from "@/lib/useOrqisStream";
import type { LogEvent, Incident, TraceEvent, ChangeLogEntry, GithubConnectInfo } from "@/lib/types";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area,
} from "recharts";

const WS_URL  = process.env.NEXT_PUBLIC_WS_URL  ?? "ws://localhost:8000/ws";
const API_URL = process.env.NEXT_PUBLIC_API_URL  ?? "http://localhost:8000";

// ── colour tokens ────────────────────────────────────────────────────────────
const C = {
  green:  "#00ff88",
  amber:  "#ffaa00",
  red:    "#ff3333",
  blue:   "#4d94ff",
  white:  "#ffffff",
  dim:    "#444444",
  dimmer: "#222222",
  bg:     "#000000",
  bg2:    "#080808",
  bg3:    "#111111",
  border: "rgba(255,255,255,0.07)",
};

const LEVEL_COLOR: Record<string, string> = {
  DEBUG:    C.dim,
  INFO:     "#888888",
  WARNING:  C.amber,
  ERROR:    C.red,
  CRITICAL: C.red,
};

const TYPE_COLOR: Record<string, string> = {
  CONNECTION:     C.blue,
  AUTHENTICATION: C.amber,
  RATE_LIMIT:     C.amber,
  TIMEOUT:        C.amber,
  MEMORY:         C.red,
  RECURSION:      C.red,
  HTTP_ERROR:     C.red,
  TRACEBACK:      C.red,
  TYPE_ERROR:     "#cc77ff",
  VALUE_ERROR:    "#cc77ff",
  ATTRIBUTE_ERROR:"#cc77ff",
  IMPORT_ERROR:   "#cc77ff",
  TOOL_FAILURE:   C.amber,
  SYNTAX_ERROR:   C.red,
  PERMISSION_ERROR: C.amber,
  GENERIC:        C.dim,
};

// ── shared style primitives ──────────────────────────────────────────────────
const mono: React.CSSProperties = { fontFamily: "'DM Mono', monospace" };
const inter: React.CSSProperties = { fontFamily: "'Inter', sans-serif" };

const primaryBtn = (color: string, loading: boolean): React.CSSProperties => ({
  ...inter,
  padding: "7px 18px",
  borderRadius: 7,
  border: `1px solid ${color}40`,
  background: `${color}12`,
  color,
  fontSize: 12,
  fontWeight: 600,
  cursor: loading ? "not-allowed" : "pointer",
  transition: "all 0.15s",
});

const ghostBtn = (loading: boolean): React.CSSProperties => ({
  ...inter,
  padding: "7px 18px",
  borderRadius: 7,
  border: `1px solid ${C.border}`,
  background: "transparent",
  color: C.dim,
  fontSize: 12,
  cursor: loading ? "not-allowed" : "pointer",
  transition: "all 0.15s",
});

// Pull a human-readable message out of whatever an action threw. The API
// helpers reject with the response body, which is usually {"detail": "..."}.
function errorMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON — use the raw text
  }
  return raw || "Something went wrong. Please try again.";
}

// Copy text to the clipboard with a graceful fallback for browsers/contexts
// where the async Clipboard API is unavailable or rejects (unfocused document,
// non-secure origin, older browsers). Throws only if every method fails.
async function copyToClipboard(text: string): Promise<void> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // fall through to the legacy path
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    const ok = document.execCommand("copy");
    if (!ok) throw new Error("copy command rejected");
  } finally {
    document.body.removeChild(ta);
  }
}

function Panel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: C.bg3,
      border: `1px solid ${C.border}`,
      borderRadius: 12,
      overflow: "hidden",
      ...style,
    }}>
      {children}
    </div>
  );
}

function PanelHeader({ label, right }: { label: string; right?: React.ReactNode }) {
  return (
    <div style={{
      padding: "10px 16px",
      borderBottom: `1px solid ${C.border}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      background: C.bg2,
    }}>
      <span style={{ ...mono, fontSize: 10, color: C.dim, letterSpacing: "0.1em", textTransform: "uppercase" as const }}>{label}</span>
      {right}
    </div>
  );
}

function LiveDot({ color = C.green }: { color?: string }) {
  return (
    <span style={{
      display: "inline-block",
      width: 7, height: 7,
      borderRadius: "50%",
      background: color,
      animation: "pulse-slow 2s ease-in-out infinite",
    }} />
  );
}

// Incidents Orqis is still working or waiting on a human for. Includes the
// GitHub PR-first states (pr_open while a PR awaits review, pr_failed and
// patch_stale which need a retry).
const ACTIVE_STATUSES = new Set<string>([
  "open", "patching", "patched", "low_confidence", "pr_open", "pr_failed", "patch_stale",
]);

// Terminal "win" states: a fix the human accepted (approved, local flow) or a
// merged fix PR (resolved, GitHub flow).
const HEALED_STATUSES = new Set<string>(["approved", "resolved"]);

// ── KPI bar ──────────────────────────────────────────────────────────────────
function KpiBar({ events, incidents, connected }: {
  events: LogEvent[];
  incidents: Incident[];
  connected: boolean;
}) {
  const errors   = events.filter(e => e.is_error).length;
  const warnings = events.filter(e => e.level === "WARNING").length;
  const open     = incidents.filter(i => ACTIVE_STATUSES.has(i.status)).length;
  const healed   = incidents.filter(i => HEALED_STATUSES.has(i.status)).length;

  const kpis = [
    { label: "ERRORS",   val: errors,    color: C.red   },
    { label: "WARNINGS", val: warnings,  color: C.amber },
    { label: "ACTIVE",   val: open,      color: C.amber },
    { label: "HEALED",   val: healed,    color: C.green },
  ];

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 2,
      padding: "0 20px",
      height: 54,
      borderBottom: `1px solid ${C.border}`,
      background: C.bg2,
      overflowX: "auto" as const,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginRight: 20, flexShrink: 0 }}>
        <LiveDot color={connected ? C.green : C.red} />
        <span style={{ ...mono, fontSize: 11, color: connected ? C.green : C.red }}>
          {connected ? "LIVE" : "RECONNECTING"}
        </span>
      </div>

      {kpis.map((k, i) => (
        <div key={i} style={{
          display: "flex",
          alignItems: "baseline",
          gap: 6,
          padding: "0 16px",
          borderLeft: `1px solid ${C.border}`,
          flexShrink: 0,
        }}>
          <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 22, color: k.color, lineHeight: 1 }}>
            {k.val}
          </span>
          <span style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em" }}>{k.label}</span>
        </div>
      ))}
    </div>
  );
}

// ── log row ──────────────────────────────────────────────────────────────────
function LogRow({ event, flash }: { event: LogEvent; flash: boolean }) {
  const levelColor = LEVEL_COLOR[event.level] ?? C.white;
  const typeColor  = event.error_type ? (TYPE_COLOR[event.error_type] ?? C.red) : undefined;

  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "5px 14px",
      borderBottom: `1px solid rgba(255,255,255,0.025)`,
      alignItems: "flex-start",
      background: flash ? "rgba(0,255,136,0.04)" : "transparent",
      transition: "background 0.8s ease",
      animation: "log-slide-in 0.2s ease-out",
    }}>
      {/* timestamp */}
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0, paddingTop: 2 }}>
        {new Date(event.timestamp).toLocaleTimeString("en", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>

      {/* level badge */}
      <span style={{
        ...mono, fontSize: 9,
        padding: "2px 6px", borderRadius: 4,
        background: levelColor + "18",
        color: levelColor,
        flexShrink: 0,
        letterSpacing: "0.06em",
        minWidth: 52,
        textAlign: "center" as const,
      }}>
        {event.level}
      </span>

      {/* error type badge */}
      {event.error_type && typeColor && (
        <span style={{
          ...mono, fontSize: 9,
          padding: "2px 6px", borderRadius: 4,
          background: typeColor + "18",
          color: typeColor,
          flexShrink: 0,
          letterSpacing: "0.06em",
          minWidth: 80,
          textAlign: "center" as const,
        }}>
          {event.error_type}
        </span>
      )}

      {/* source */}
      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{event.source}</span>

      {/* message */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ ...mono, fontSize: 12, color: event.is_error ? "#dddddd" : "#666666", wordBreak: "break-all" as const }}>
          {event.raw_line.length > 200 ? event.raw_line.slice(0, 200) + "…" : event.raw_line}
        </div>
        {event.interpretation && (
          <div style={{ ...inter, fontSize: 11, color: C.green, marginTop: 3, opacity: 0.85 }}>
            ↳ {event.interpretation}
          </div>
        )}
      </div>
    </div>
  );
}

// ── diff viewer ───────────────────────────────────────────────────────────────
function DiffViewer({ diff }: { diff: string }) {
  return (
    <div style={{ padding: "8px 0" }}>
      {diff.split("\n").map((line, i) => {
        const isAdd = line.startsWith("+") && !line.startsWith("+++");
        const isRem = line.startsWith("-") && !line.startsWith("---");
        const isAt  = line.startsWith("@@");
        return (
          <div key={i} style={{
            display: "flex",
            background: isAdd ? "rgba(0,255,136,0.07)" : isRem ? "rgba(255,51,51,0.07)" : "transparent",
            borderLeft: `3px solid ${isAdd ? C.green : isRem ? C.red : "transparent"}`,
          }}>
            <span style={{
              ...mono, fontSize: 11,
              color: isAdd ? C.green : isRem ? C.red : isAt ? C.blue : C.dim,
              padding: "2px 12px",
              userSelect: "none" as const,
              minWidth: 16,
            }}>
              {isAdd ? "+" : isRem ? "−" : " "}
            </span>
            <span style={{
              ...mono, fontSize: 11,
              color: isAdd ? "rgba(0,255,136,0.9)" : isRem ? "rgba(255,51,51,0.8)" : isAt ? C.blue : "#555",
              padding: "2px 8px 2px 0",
              wordBreak: "break-all" as const,
            }}>
              {line.slice(1) || line}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── incident card ─────────────────────────────────────────────────────────────
function IncidentCard({
  incident,
  highlighted,
  onApprove,
  onDismiss,
  onOpenPr,
  onResolve,
  onCopyPrompt,
}: {
  incident: Incident;
  highlighted?: boolean;
  onApprove: (id: string, force?: boolean) => Promise<unknown>;
  onDismiss: (id: string) => Promise<unknown>;
  onOpenPr: (id: string) => Promise<unknown>;
  onResolve: (id: string) => Promise<unknown>;
  onCopyPrompt: (id: string) => Promise<string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const statusColor = {
    open:           C.amber,
    patching:       C.blue,
    patched:        C.green,
    low_confidence: C.amber,
    approved:       C.green,
    dismissed:      C.dim,
    pr_open:        C.blue,
    pr_failed:      C.red,
    patch_stale:    C.amber,
    resolved:       C.green,
  }[incident.status] ?? C.dim;

  const isActive = ACTIVE_STATUSES.has(incident.status);

  const isLowConf = incident.status === "low_confidence";
  const isGithub = !!incident.repo_full_name;
  const canRetryPr = incident.status === "pr_failed" || incident.status === "patch_stale";
  const conf = incident.confidence;
  const confColor = conf == null ? C.dim : conf >= 70 ? C.green : conf >= 50 ? C.amber : C.red;

  // Run an action, surfacing any failure inline instead of letting it become an
  // unhandled promise rejection (which leaves the user with no feedback).
  async function runAction(fn: () => Promise<unknown>) {
    setLoading(true);
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  const handleApprove = () => runAction(() => onApprove(incident.id, isLowConf));
  const handleDismiss = () => runAction(() => onDismiss(incident.id));
  const handleOpenPr = () => runAction(() => onOpenPr(incident.id));
  const handleResolve = () => runAction(() => onResolve(incident.id));
  async function handleCopyPrompt() {
    try {
      const prompt = await onCopyPrompt(incident.id);
      await copyToClipboard(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopyFailed(true);
      setTimeout(() => setCopyFailed(false), 2500);
    }
  }

  return (
    <div style={{
      background: isActive ? C.bg2 : "transparent",
      border: `1px solid ${highlighted ? C.green : isActive ? statusColor + "30" : C.border}`,
      borderRadius: 10,
      marginBottom: 8,
      overflow: "hidden",
      transition: "border-color 0.3s ease",
      boxShadow: highlighted ? `0 0 0 1px ${C.green}40` : "none",
      animation: incident.status === "open" ? "row-pulse 3s ease-in-out infinite" : "none",
    }}>
      {/* header row */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", cursor: "pointer" }}
        onClick={() => setExpanded(x => !x)}
      >
        <LiveDot color={statusColor} />

        <span style={{
          ...mono, fontSize: 9,
          padding: "2px 7px", borderRadius: 4,
          background: statusColor + "18",
          color: statusColor,
          letterSpacing: "0.06em",
          flexShrink: 0,
        }}>
          {incident.status.toUpperCase()}
        </span>

        {incident.hit_count > 1 && (
          <span style={{ ...mono, fontSize: 10, color: C.red, flexShrink: 0 }}>×{incident.hit_count}</span>
        )}

        {conf != null && (
          <span style={{
            ...mono, fontSize: 9,
            padding: "2px 7px", borderRadius: 4,
            background: confColor + "18",
            color: confColor,
            letterSpacing: "0.04em",
            flexShrink: 0,
          }}>
            {conf}/100
          </span>
        )}

        {incident.error_type && (
          <span style={{ ...mono, fontSize: 9, color: TYPE_COLOR[incident.error_type] ?? C.dim, flexShrink: 0 }}>
            [{incident.error_type}]
          </span>
        )}

        <span style={{ ...inter, fontSize: 12, color: "#888", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
          {incident.error_message.slice(0, 120)}
        </span>

        {(incident.repo_relative_path || incident.file_path) && (
          <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>
            {(incident.repo_relative_path || incident.file_path || "")
              .replace(/\\/g, "/").split("/").slice(-2).join("/")}{incident.error_line ? `:${incident.error_line}` : ""}
          </span>
        )}

        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* expanded body */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${C.border}`, padding: "12px 14px" }}>
          {incident.interpretation && (
            <div style={{ ...inter, fontSize: 12, color: C.green, marginBottom: 12 }}>
              {incident.interpretation}
            </div>
          )}

          {/* code context */}
          {incident.code_context && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                CODE CONTEXT · {incident.function_name}() · line {incident.context_start_line}
              </div>
              <div style={{
                background: C.bg,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                padding: "8px 0",
                overflowX: "auto" as const,
              }}>
                {incident.code_context.split("\n").map((line, i) => {
                  const lineno = (incident.context_start_line ?? 1) + i;
                  const isErr  = lineno === incident.error_line;
                  return (
                    <div key={i} style={{
                      display: "flex",
                      gap: 12,
                      padding: "2px 12px",
                      background: isErr ? "rgba(255,51,51,0.08)" : "transparent",
                      borderLeft: `3px solid ${isErr ? C.red : "transparent"}`,
                    }}>
                      <span style={{ ...mono, fontSize: 11, color: C.dimmer, minWidth: 32, textAlign: "right" as const, userSelect: "none" as const }}>
                        {lineno}
                      </span>
                      <span style={{ ...mono, fontSize: 11, color: isErr ? "#dddddd" : "#555" }}>{line}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* verification results */}
          {(incident.validation_errors?.length > 0 || incident.validation_warnings?.length > 0) && (
            <div style={{
              marginBottom: 12,
              background: C.bg,
              border: `1px solid ${(isLowConf ? C.red : C.amber) + "30"}`,
              borderRadius: 6,
              padding: "8px 12px",
            }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                VERIFICATION {isLowConf ? "· FAILED" : "· WARNINGS"}
              </div>
              {incident.validation_errors?.map((e, i) => (
                <div key={`e${i}`} style={{ ...mono, fontSize: 11, color: C.red, lineHeight: 1.6 }}>
                  ✗ {e}
                </div>
              ))}
              {incident.validation_warnings?.map((w, i) => (
                <div key={`w${i}`} style={{ ...mono, fontSize: 11, color: C.amber, lineHeight: 1.6 }}>
                  ⚠ {w}
                </div>
              ))}
            </div>
          )}

          {/* diff */}
          {incident.diff && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                SUGGESTED FIX
              </div>
              <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, overflowX: "auto" as const }}>
                <DiffViewer diff={incident.diff} />
              </div>
            </div>
          )}

          {/* PR error / stale notice */}
          {incident.pr_error && (canRetryPr) && (
            <div style={{
              ...mono, fontSize: 11, color: C.amber, marginBottom: 10,
              background: C.bg, border: `1px solid ${C.amber}30`, borderRadius: 6, padding: "8px 12px",
            }}>
              ⚠ {incident.pr_error}
            </div>
          )}

          {/* action buttons */}
          <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" as const }}>
            {/* GitHub PR-first flow */}
            {isGithub && incident.pr_url && (
              <a
                href={incident.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  ...inter, padding: "7px 18px", borderRadius: 7,
                  border: `1px solid ${C.blue}40`, background: `${C.blue}12`,
                  color: C.blue, fontSize: 12, fontWeight: 600, textDecoration: "none",
                }}
              >
                {incident.status === "resolved" ? "View merged PR" : `Review PR #${incident.pr_number} →`}
              </a>
            )}

            {isGithub && incident.status === "pr_open" && (
              <button onClick={handleResolve} disabled={loading} style={ghostBtn(loading)}>
                Mark resolved
              </button>
            )}

            {isGithub && canRetryPr && incident.diff && (
              <button onClick={handleOpenPr} disabled={loading} style={primaryBtn(C.amber, loading)}>
                {loading ? "Retrying…" : "Retry PR →"}
              </button>
            )}

            {isGithub && incident.status === "low_confidence" && incident.diff && (
              <button onClick={handleOpenPr} disabled={loading} style={primaryBtn(C.amber, loading)}>
                {loading ? "Opening…" : "Open PR (low confidence) →"}
              </button>
            )}

            {/* Local-dev apply path (no repo mapped) */}
            {!isGithub && isActive && incident.diff && (
              <button onClick={handleApprove} disabled={loading} style={primaryBtn(isLowConf ? C.amber : C.green, loading)}>
                {loading ? "Applying…" : isLowConf ? "Force Apply (low confidence) →" : "Apply Fix →"}
              </button>
            )}

            {/* IDE-agnostic: paste into any AI assistant chat */}
            {incident.diff && incident.status !== "resolved" && (
              <button onClick={handleCopyPrompt} disabled={loading} style={ghostBtn(loading)}>
                {copied ? "Copied — paste in your IDE" : copyFailed ? "Copy failed — retry" : "Copy for AI assistant"}
              </button>
            )}

            {isActive && (
              <button onClick={handleDismiss} disabled={loading} style={ghostBtn(loading)}>
                Dismiss
              </button>
            )}
          </div>

          {actionError && (
            <div style={{
              ...mono, fontSize: 11, color: C.red, marginTop: 10,
              background: C.bg, border: `1px solid ${C.red}30`, borderRadius: 6, padding: "8px 12px",
            }}>
              ✕ {actionError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── error rate sparkline data ─────────────────────────────────────────────────
function buildSparkline(events: LogEvent[]) {
  const buckets: { label: string; errors: number; total: number }[] = [];
  const now = Date.now();
  for (let i = 9; i >= 0; i--) {
    buckets.push({ label: `-${(i + 1) * 6}s`, errors: 0, total: 0 });
  }
  for (const e of events) {
    const age = (now - new Date(e.timestamp).getTime()) / 1000;
    if (age > 60) continue;
    const bucket = Math.min(9, Math.floor(age / 6));
    buckets[9 - bucket].total++;
    if (e.is_error) buckets[9 - bucket].errors++;
  }
  return buckets;
}

// ── connected GitHub account / repo badge ─────────────────────────────────────
function GithubBadge({ github }: { github: GithubConnectInfo | null }) {
  const base: React.CSSProperties = {
    ...mono, fontSize: 11, textDecoration: "none",
    display: "flex", alignItems: "center", gap: 6,
    padding: "4px 10px", borderRadius: 7, border: `1px solid ${C.border}`,
  };

  if (github?.connected) {
    const repoCount = github.repos.length;
    const label =
      repoCount === 1 ? github.repos[0]
      : repoCount > 1 ? `${github.account_login ?? "github"} · ${repoCount} repos`
      : (github.account_login ?? "connected");
    return (
      <a href="/settings" title={`Connected to GitHub${github.account_login ? ` as ${github.account_login}` : ""}: ${github.repos.join(", ") || "no repos"}`}
         style={{ ...base, color: C.green, borderColor: `${C.green}40`, background: `${C.green}10` }}>
        <span style={{ fontSize: 12 }}>⎇</span>
        <span style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>{label}</span>
      </a>
    );
  }

  if (github?.configured) {
    return (
      <a href="/settings" style={{ ...base, color: C.amber, borderColor: `${C.amber}40`, background: `${C.amber}10` }}>
        <span style={{ fontSize: 12 }}>⎇</span> Connect GitHub
      </a>
    );
  }

  // GitHub App not configured on this backend — local-only mode.
  return (
    <a href="/settings" title="GitHub App not configured — fixes apply to your local working copy"
       style={{ ...base, color: C.dim }}>
      <span style={{ fontSize: 12 }}>⎇</span> Local mode
    </a>
  );
}

// ── change-log row ────────────────────────────────────────────────────────────
const CHANGE_META: Record<string, { label: string; color: string; icon: string }> = {
  fix_applied: { label: "APPLIED LOCALLY", color: C.green, icon: "✎" },
  pr_opened:   { label: "PR OPENED",       color: C.blue,  icon: "⤴" },
  pr_merged:   { label: "PR MERGED",        color: C.green, icon: "✓" },
  resolved:    { label: "RESOLVED",         color: C.green, icon: "✓" },
  dismissed:   { label: "DISMISSED",        color: C.dim,   icon: "—" },
  pr_failed:   { label: "PR FAILED",        color: C.red,   icon: "!" },
  patch_stale: { label: "PATCH STALE",      color: C.amber, icon: "△" },
};

function ChangeRow({
  change,
  onViewIncident,
}: {
  change: ChangeLogEntry;
  onViewIncident: (incidentId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = CHANGE_META[change.action] ?? { label: change.action.toUpperCase(), color: C.dim, icon: "•" };
  const when = new Date(change.timestamp);
  const timeLabel = when.toLocaleDateString() === new Date().toLocaleDateString()
    ? when.toLocaleTimeString("en", { hour12: false })
    : when.toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  return (
    <div style={{
      marginBottom: 8,
      background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8,
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "10px 14px", cursor: change.diff ? "pointer" : "default",
      }}
        onClick={() => change.diff && setExpanded(x => !x)}
      >
        <span style={{ color: meta.color, fontSize: 14, width: 16, textAlign: "center" as const, flexShrink: 0 }}>{meta.icon}</span>
        <span style={{
          ...mono, fontSize: 9, letterSpacing: "0.08em", flexShrink: 0,
          padding: "3px 7px", borderRadius: 4,
          background: meta.color + "18", color: meta.color, minWidth: 104, textAlign: "center" as const,
        }}>
          {meta.label}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...inter, fontSize: 13, color: C.white, whiteSpace: "nowrap" as const, overflow: "hidden", textOverflow: "ellipsis" }}>
            {change.summary}
          </div>
          <div style={{ ...mono, fontSize: 10, color: C.dim, marginTop: 2 }}>
            {change.repo_full_name ? `${change.repo_full_name} · ` : ""}
            {change.file ?? "—"}
            {change.applied_locally ? " · written to disk" : ""}
            {change.error_type ? ` · ${change.error_type}` : ""}
          </div>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onViewIncident(change.incident_id); }}
          style={{
            ...mono, fontSize: 10, color: C.blue, background: "transparent",
            border: `1px solid ${C.blue}40`, borderRadius: 5, padding: "4px 8px", cursor: "pointer", flexShrink: 0,
          }}
        >
          View issue
        </button>
        {change.pr_url && (
          <a href={change.pr_url} target="_blank" rel="noopener noreferrer"
             onClick={e => e.stopPropagation()}
             style={{ ...mono, fontSize: 11, color: C.blue, textDecoration: "none", flexShrink: 0 }}>
            PR{change.pr_number ? ` #${change.pr_number}` : ""} →
          </a>
        )}
        <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0 }}>
          {timeLabel}{change.diff ? (expanded ? " ▲" : " ▼") : ""}
        </span>
      </div>
      {expanded && change.diff && (
        <div style={{
          padding: "0 14px 12px",
          borderTop: `1px solid ${C.border}`,
        }}>
          <pre style={{
            ...mono, fontSize: 10, color: "#aaa", margin: "10px 0 0",
            whiteSpace: "pre-wrap" as const, wordBreak: "break-all" as const,
            maxHeight: 220, overflow: "auto" as const,
            background: C.bg, padding: 10, borderRadius: 6,
          }}>
            {change.diff}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── trace row ─────────────────────────────────────────────────────────────────
function TraceRow({ trace }: { trace: TraceEvent }) {
  const kindColor = trace.is_error ? C.red : trace.kind.includes("end") ? C.green : C.blue;
  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "6px 14px",
      borderBottom: `1px solid rgba(255,255,255,0.025)`,
      alignItems: "center",
    }}>
      <span style={{ ...mono, fontSize: 10, color: C.dimmer, flexShrink: 0 }}>
        {new Date(trace.timestamp).toLocaleTimeString("en", { hour12: false })}
      </span>
      <span style={{
        ...mono, fontSize: 9, padding: "2px 6px", borderRadius: 4,
        background: kindColor + "18", color: kindColor, flexShrink: 0,
        minWidth: 72, textAlign: "center" as const,
      }}>
        {trace.kind}
      </span>
      <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.provider}</span>
      {trace.model && <span style={{ ...mono, fontSize: 10, color: "#555", flexShrink: 0 }}>{trace.model}</span>}
      {trace.tool_name && (
        <span style={{ ...mono, fontSize: 10, color: C.blue, flexShrink: 0 }}>{trace.tool_name}()</span>
      )}
      {(trace.input_tokens != null || trace.output_tokens != null) && (
        <span style={{ ...mono, fontSize: 10, color: "#555", flexShrink: 0 }}>
          {trace.input_tokens ?? 0}→{trace.output_tokens ?? 0} tok
        </span>
      )}
      {trace.cost_usd != null && (
        <span style={{ ...mono, fontSize: 10, color: trace.cost_usd > 0.1 ? C.amber : C.green, marginLeft: "auto", flexShrink: 0 }}>
          ${trace.cost_usd.toFixed(4)}
        </span>
      )}
      {trace.latency_ms != null && (
        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{trace.latency_ms}ms</span>
      )}
    </div>
  );
}

// ── main dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { events, traces, incidents, changes, github, connected, approveIncident, dismissIncident, openPr, resolveIncident, copyPrompt } =
    useOrqisStream(WS_URL, API_URL);

  const [activeTab, setActiveTab] = useState<"logs" | "incidents" | "traces" | "changes">("incidents");
  const [highlightIncidentId, setHighlightIncidentId] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const prevEventCount = useRef(0);

  // Auto-scroll log stream
  useEffect(() => {
    if (autoScroll && logRef.current && events.length > prevEventCount.current) {
      logRef.current.scrollTop = 0;
    }
    prevEventCount.current = events.length;
  }, [events.length, autoScroll]);

  // Track which event IDs are "new" for the flash animation
  const flashSet = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (events[0]) {
      flashSet.current.add(events[0].id);
      setTimeout(() => flashSet.current.delete(events[0].id), 800);
    }
  }, [events[0]?.id]);

  const sparkData = buildSparkline(events);
  const openCount = incidents.filter(i => ACTIVE_STATUSES.has(i.status)).length;
  const totalCost = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);

  const viewIncidentFromChange = useCallback((incidentId: string) => {
    setActiveTab("incidents");
    setHighlightIncidentId(incidentId);
    setTimeout(() => setHighlightIncidentId(null), 2500);
  }, []);

  const tabs = [
    { id: "incidents", label: "ISSUES & FIXES",  badge: openCount > 0 ? openCount : null },
    { id: "changes",   label: "CHANGES",         badge: changes.length > 0 ? changes.length : null },
    { id: "logs",      label: "ACTIVITY",        badge: null },
    { id: "traces",    label: "AI CALLS",        badge: null },
  ] as const;

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column" as const,
      fontFamily: "'DM Mono', monospace",
    }}>
      {/* Top bar */}
      <div style={{
        height: 54,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        borderBottom: `1px solid ${C.border}`,
        background: C.bg2,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {/* Logo */}
          <a href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
            <div style={{
              width: 26, height: 26, borderRadius: 6,
              background: "linear-gradient(135deg, #ffffff 0%, #a0a0a0 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, fontWeight: 700, color: "#000",
            }}>⌬</div>
            <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 16, color: C.white, letterSpacing: "0.03em" }}>ORQIS</span>
          </a>

          <span style={{ color: C.border, fontSize: 16 }}>/</span>
          <span style={{ ...mono, fontSize: 12, color: C.dim }}>production</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {totalCost > 0 && (
            <span style={{ ...mono, fontSize: 11, color: totalCost > 1 ? C.amber : C.green }}>
              ${totalCost.toFixed(4)} tracked
            </span>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LiveDot color={connected ? C.green : C.red} />
            <span style={{ ...mono, fontSize: 10, color: connected ? C.green : C.red }}>
              {connected ? "CONNECTED" : "OFFLINE"}
            </span>
          </div>
          <GithubBadge github={github} />
          <a href="/settings" style={{ ...mono, fontSize: 11, color: C.dim, textDecoration: "none" }}>
            ⚙ Settings
          </a>
        </div>
      </div>

      {/* Plain-English health banner — the first thing a user reads */}
      <HealthHero
        incidents={incidents}
        connected={connected}
        onViewIssues={() => setActiveTab("incidents")}
      />

      {/* KPI bar */}
      <KpiBar events={events} incidents={incidents} connected={connected} />

      {/* Main layout */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

        {/* ── left: log / incidents / traces panel ── */}
        <div style={{
          flex: 1,
          display: "flex",
          flexDirection: "column" as const,
          overflow: "hidden",
          borderRight: `1px solid ${C.border}`,
        }}>
          {/* Tabs */}
          <div style={{
            display: "flex",
            gap: 0,
            borderBottom: `1px solid ${C.border}`,
            background: C.bg2,
            flexShrink: 0,
          }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  ...mono,
                  padding: "10px 20px",
                  fontSize: 10,
                  letterSpacing: "0.1em",
                  color: activeTab === tab.id ? C.white : C.dim,
                  background: "transparent",
                  border: "none",
                  borderBottom: `2px solid ${activeTab === tab.id ? C.green : "transparent"}`,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  transition: "color 0.15s, border-color 0.15s",
                }}
              >
                {tab.label}
                {tab.badge != null && (
                  <span style={{
                    background: C.red,
                    color: C.white,
                    borderRadius: 10,
                    padding: "1px 6px",
                    fontSize: 9,
                    fontWeight: 700,
                  }}>
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}

            {activeTab === "logs" && (
              <button
                onClick={() => setAutoScroll(x => !x)}
                style={{
                  ...mono,
                  marginLeft: "auto",
                  padding: "10px 16px",
                  fontSize: 9,
                  color: autoScroll ? C.green : C.dim,
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  letterSpacing: "0.08em",
                }}
              >
                {autoScroll ? "⬆ AUTO" : "PAUSED"}
              </button>
            )}
          </div>

          {/* Content */}
          <div ref={logRef} style={{ flex: 1, overflowY: "auto" as const }}>
            {activeTab === "logs" && (
              events.length === 0
                ? <EmptyState label="Waiting for log events…" />
                : events.map(e => (
                    <LogRow key={e.id} event={e} flash={flashSet.current.has(e.id)} />
                  ))
            )}

            {activeTab === "incidents" && (
              <div style={{ padding: 14 }}>
                {incidents.length === 0
                  ? <EmptyState label="No problems found. Your app is healthy." />
                  : incidents.map(i => (
                      <IncidentCard
                        key={i.id}
                        incident={i}
                        highlighted={highlightIncidentId === i.id}
                        onApprove={approveIncident}
                        onDismiss={dismissIncident}
                        onOpenPr={openPr}
                        onResolve={resolveIncident}
                        onCopyPrompt={copyPrompt}
                      />
                    ))
                }
              </div>
            )}

            {activeTab === "changes" && (
              changes.length === 0
                ? <EmptyState label="No changes yet. When Orqis applies a fix or opens a PR, it shows up here." />
                : <div style={{ padding: 14 }}>
                    {changes.map(c => (
                      <ChangeRow key={c.id} change={c} onViewIncident={viewIncidentFromChange} />
                    ))}
                  </div>
            )}

            {activeTab === "traces" && (
              traces.length === 0
                ? <EmptyState label="No trace events yet. Add orqis.init() to your app." />
                : traces.map(t => <TraceRow key={t.id} trace={t} />)
            )}
          </div>
        </div>

        {/* ── right sidebar ── */}
        <div style={{
          width: 320,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column" as const,
          gap: 12,
          padding: 14,
          overflowY: "auto" as const,
          background: C.bg,
        }}>
          {/* Error rate sparkline */}
          <Panel>
            <PanelHeader label="Error rate · last 60s" />
            <div style={{ padding: "12px 8px 8px" }}>
              <ResponsiveContainer width="100%" height={80}>
                <AreaChart data={sparkData}>
                  <defs>
                    <linearGradient id="errGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={C.red} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={C.red} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis dataKey="label" hide />
                  <YAxis hide />
                  <Tooltip
                    contentStyle={{ background: C.bg3, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: "DM Mono", fontSize: 10 }}
                    labelStyle={{ color: C.dim }}
                    itemStyle={{ color: C.red }}
                  />
                  <Area type="monotone" dataKey="errors" stroke={C.red} strokeWidth={1.5} fill="url(#errGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          {/* Error type breakdown — only when there are actually errors */}
          {events.some(e => e.is_error) && (
            <Panel>
              <PanelHeader label="Error types" />
              <ErrorBreakdown events={events} />
            </Panel>
          )}

          {/* Cost tracker */}
          {traces.length > 0 && (
            <Panel>
              <PanelHeader label="LLM cost" />
              <CostTracker traces={traces} />
            </Panel>
          )}

          {/* Setup hint — only until the app is streaming (traces flowing) */}
          {traces.length === 0 && (
            <Panel style={{ border: `1px solid ${C.green}20` }}>
              <PanelHeader label="Connect your app" right={<span style={{ ...mono, fontSize: 9, color: C.green }}>SDK</span>} />
              <div style={{ padding: "12px 14px" }}>
                <div style={{ ...mono, fontSize: 10, color: C.dim, marginBottom: 8 }}>Instrument in one line:</div>
                <div style={{
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "10px 12px",
                }}>
                  <div style={{ ...mono, fontSize: 11, color: "#cc77ff" }}>import <span style={{ color: C.green }}>orqis</span></div>
                  <div style={{ ...mono, fontSize: 11, color: C.green }}>orqis<span style={{ color: C.white }}>.init()</span></div>
                </div>
                <div style={{ ...inter, fontSize: 11, color: C.dim, marginTop: 10, lineHeight: 1.6 }}>
                  Auto-patches OpenAI, Anthropic &amp; LangChain. Zero config.
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

// ── health hero ───────────────────────────────────────────────────────────────
// The one element a non-technical user reads first: is my app okay?
function HealthHero({
  incidents,
  connected,
  onViewIssues,
}: {
  incidents: Incident[];
  connected: boolean;
  onViewIssues: () => void;
}) {
  const prReady = incidents.filter(i => i.status === "pr_open").length;
  const needsAttention = incidents.filter(
    i => i.status === "pr_failed" || i.status === "patch_stale",
  ).length;
  const needsYou = incidents.filter(
    i =>
      i.status === "patched" ||
      i.status === "low_confidence" ||
      i.status === "pr_open" ||
      i.status === "pr_failed" ||
      i.status === "patch_stale",
  ).length;
  const fixing = incidents.filter(i => i.status === "open" || i.status === "patching").length;
  const healed = incidents.filter(i => HEALED_STATUSES.has(i.status)).length;

  let tone: string, title: string, sub: string;
  if (!connected) {
    tone = C.dim;
    title = "Connecting to your app…";
    sub = "Waiting for the Orqis monitor to come online.";
  } else if (needsYou > 0) {
    tone = C.amber;
    title = needsYou === 1 ? "1 fix is ready for you" : `${needsYou} fixes are ready for you`;
    sub = needsAttention > 0
      ? "A fix PR needs another look — open it to retry."
      : prReady > 0
        ? "Orqis opened a fix PR. Review and merge it to ship the fix."
        : "Orqis found the bug and wrote a fix. Review it to apply.";
  } else if (fixing > 0) {
    tone = C.blue;
    title = fixing === 1 ? "Looking into 1 problem" : `Looking into ${fixing} problems`;
    sub = "Orqis spotted an error and is figuring out the fix right now.";
  } else {
    tone = C.green;
    title = "Everything's running smoothly";
    sub = "No errors right now. Orqis is watching your app in the background.";
  }

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 20,
      padding: "20px 24px",
      borderBottom: `1px solid ${C.border}`,
      background: `linear-gradient(90deg, ${tone}0c 0%, transparent 60%)`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: tone + "1a",
          border: `1px solid ${tone}40`,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <LiveDot color={tone} />
        </div>
        <div>
          <div style={{
            fontFamily: "'Anton', sans-serif",
            fontSize: 24, color: C.white, letterSpacing: "0.01em", lineHeight: 1.1,
          }}>
            {title}
          </div>
          <div style={{ ...inter, fontSize: 13, color: C.dim, marginTop: 4 }}>
            {sub}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 24, flexShrink: 0 }}>
        {healed > 0 && (
          <div style={{ textAlign: "right" as const }}>
            <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 26, color: C.green, lineHeight: 1 }}>
              {healed}
            </div>
            <div style={{ ...inter, fontSize: 11, color: C.dim }}>auto-fixed</div>
          </div>
        )}
        {needsYou > 0 && (
          <button
            onClick={onViewIssues}
            style={{
              ...inter,
              padding: "11px 22px",
              borderRadius: 9,
              border: `1px solid ${C.amber}55`,
              background: `${C.amber}14`,
              color: C.amber,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Review fixes →
          </button>
        )}
      </div>
    </div>
  );
}

// ── supporting sub-components ─────────────────────────────────────────────────

function EmptyState({ label }: { label: string }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column" as const,
      alignItems: "center",
      justifyContent: "center",
      height: 200,
      gap: 12,
      opacity: 0.4,
    }}>
      <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 32, color: C.dim }}>⌬</div>
      <span style={{ ...mono, fontSize: 11, color: C.dim }}>{label}</span>
    </div>
  );
}

function ErrorBreakdown({ events }: { events: LogEvent[] }) {
  const counts: Record<string, number> = {};
  for (const e of events) {
    if (e.error_type) counts[e.error_type] = (counts[e.error_type] ?? 0) + 1;
  }
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  if (sorted.length === 0) {
    return <div style={{ ...mono, fontSize: 10, color: C.dim, padding: "12px 14px" }}>No errors yet.</div>;
  }
  const max = sorted[0][1];
  return (
    <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column" as const, gap: 6 }}>
      {sorted.map(([type, count]) => {
        const color = TYPE_COLOR[type] ?? C.dim;
        return (
          <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ ...mono, fontSize: 10, color, minWidth: 100 }}>{type}</span>
            <div style={{ flex: 1, background: C.bg, borderRadius: 3, height: 4, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width: `${(count / max) * 100}%`,
                background: color,
                borderRadius: 3,
                transition: "width 0.4s ease",
              }} />
            </div>
            <span style={{ ...mono, fontSize: 10, color: C.dim, minWidth: 20, textAlign: "right" as const }}>{count}</span>
          </div>
        );
      })}
    </div>
  );
}

function CostTracker({ traces }: { traces: TraceEvent[] }) {
  const total = traces.reduce((s, t) => s + (t.cost_usd ?? 0), 0);
  const byProvider: Record<string, number> = {};
  for (const t of traces) {
    if (t.cost_usd) byProvider[t.provider] = (byProvider[t.provider] ?? 0) + t.cost_usd;
  }
  const provColors: Record<string, string> = { openai: C.green, anthropic: C.blue, langchain: C.amber };

  return (
    <div style={{ padding: "12px 14px" }}>
      <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 28, color: total > 1 ? C.amber : C.green, marginBottom: 10 }}>
        ${total.toFixed(4)}
      </div>
      {Object.entries(byProvider).map(([p, cost]) => (
        <div key={p} style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ ...mono, fontSize: 10, color: provColors[p] ?? C.dim }}>{p}</span>
          <span style={{ ...mono, fontSize: 10, color: C.dim }}>${cost.toFixed(4)}</span>
        </div>
      ))}
    </div>
  );
}
