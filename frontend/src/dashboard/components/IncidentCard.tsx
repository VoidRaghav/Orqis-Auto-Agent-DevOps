"use client";

import { useState } from "react";
import type { Incident } from "@/lib/types";
import { C, ACTIVE_STATUSES, TYPE_COLOR } from "../constants";
import { mono, inter, primaryBtn, ghostBtn, errorMessage, copyToClipboard } from "../shared";
import DiffViewer from "./DiffViewer";
import IncidentTimeline from "./IncidentTimeline";
import { LiveDot } from "./ui";

export default function IncidentCard({
  incident,
  index,
  highlighted,
  onApprove,
  onDismiss,
  onOpenPr,
  onResolve,
  onCopyPrompt,
}: {
  incident: Incident;
  index?: number;
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

  const statusColor =
    {
      open: C.amber,
      patching: C.blue,
      patched: C.green,
      low_confidence: C.amber,
      needs_action: C.amber,
      approved: C.green,
      dismissed: C.dim,
      pr_open: C.blue,
      pr_failed: C.red,
      patch_stale: C.amber,
      resolved: C.green,
    }[incident.status] ?? C.dim;

  const isActive = ACTIVE_STATUSES.has(incident.status);
  const isLowConf = incident.status === "low_confidence";
  const isGithub = !!incident.repo_full_name;
  const canRetryPr = incident.status === "pr_failed" || incident.status === "patch_stale";
  const conf = incident.confidence;
  const confColor = conf == null ? C.dim : conf >= 70 ? C.green : conf >= 50 ? C.amber : C.red;

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
    <div
      style={{
        background: isActive ? C.bg2 : "transparent",
        border: `1px solid ${highlighted ? C.green : isActive ? statusColor + "30" : C.border}`,
        borderRadius: 10,
        marginBottom: 8,
        overflow: "hidden",
        transition: "border-color 0.3s ease",
        boxShadow: highlighted ? `0 0 0 1px ${C.green}40` : "none",
        animation: incident.status === "open" ? "row-pulse 3s ease-in-out infinite" : "none",
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", cursor: "pointer" }}
        onClick={() => setExpanded((x) => !x)}
      >
        {index != null ? (
          <span
            className="incident-index"
            style={{
              ...mono,
              color: statusColor,
              borderColor: `${statusColor}44`,
              background: `${statusColor}14`,
            }}
          >
            {index}
          </span>
        ) : (
          <LiveDot color={statusColor} />
        )}

        <span
          style={{
            ...mono,
            fontSize: 9,
            padding: "2px 7px",
            borderRadius: 4,
            background: statusColor + "18",
            color: statusColor,
            letterSpacing: "0.06em",
            flexShrink: 0,
          }}
        >
          {incident.status.replace(/_/g, " ").toUpperCase()}
        </span>

        {incident.hit_count > 1 && (
          <span style={{ ...mono, fontSize: 10, color: C.red, flexShrink: 0 }}>×{incident.hit_count}</span>
        )}

        {conf != null && (
          <span
            style={{
              ...mono,
              fontSize: 9,
              padding: "2px 7px",
              borderRadius: 4,
              background: confColor + "18",
              color: confColor,
              letterSpacing: "0.04em",
              flexShrink: 0,
            }}
          >
            {conf}/100
          </span>
        )}

        {incident.error_type && (
          <span style={{ ...mono, fontSize: 9, color: TYPE_COLOR[incident.error_type] ?? C.dim, flexShrink: 0 }}>
            [{incident.error_type}]
          </span>
        )}

        <span
          style={{
            ...inter,
            fontSize: 12,
            color: "#888",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {incident.error_message.slice(0, 120)}
        </span>

        {(incident.repo_relative_path || incident.file_path) && (
          <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>
            {(incident.repo_relative_path || incident.file_path || "")
              .replace(/\\/g, "/")
              .split("/")
              .slice(-2)
              .join("/")}
            {incident.error_line ? `:${incident.error_line}` : ""}
          </span>
        )}

        <span style={{ ...mono, fontSize: 10, color: C.dim, flexShrink: 0 }}>{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <>
          <IncidentTimeline incident={incident} />
          {incident.status === "patch_stale" && (
            <p style={{ ...mono, fontSize: 11, color: C.amber, marginBottom: 8 }}>
              Base branch moved — retry PR to rebase the fix onto current HEAD.
            </p>
          )}
        <div style={{ borderTop: `1px solid ${C.border}`, padding: "12px 14px" }}>
          {incident.interpretation && (
            <div style={{ ...inter, fontSize: 12, color: C.green, marginBottom: 12 }}>{incident.interpretation}</div>
          )}

          {incident.code_context && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                CODE CONTEXT · {incident.function_name}() · line {incident.context_start_line}
              </div>
              <div
                style={{
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding: "8px 0",
                  overflowX: "auto",
                }}
              >
                {incident.code_context.split("\n").map((line, i) => {
                  const lineno = (incident.context_start_line ?? 1) + i;
                  const isErr = lineno === incident.error_line;
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: 12,
                        padding: "2px 12px",
                        background: isErr ? "rgba(255,51,51,0.08)" : "transparent",
                        borderLeft: `3px solid ${isErr ? C.red : "transparent"}`,
                      }}
                    >
                      <span
                        style={{
                          ...mono,
                          fontSize: 11,
                          color: C.dimmer,
                          minWidth: 32,
                          textAlign: "right",
                          userSelect: "none",
                        }}
                      >
                        {lineno}
                      </span>
                      <span style={{ ...mono, fontSize: 11, color: isErr ? "#dddddd" : "#555" }}>{line}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {(incident.validation_errors?.length > 0 || incident.validation_warnings?.length > 0) && (
            <div
              style={{
                marginBottom: 12,
                background: C.bg,
                border: `1px solid ${(isLowConf ? C.red : C.amber) + "30"}`,
                borderRadius: 6,
                padding: "8px 12px",
              }}
            >
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

          {incident.diff && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ ...mono, fontSize: 9, color: C.dim, letterSpacing: "0.08em", marginBottom: 6 }}>
                SUGGESTED FIX
              </div>
              <div
                style={{
                  background: C.bg,
                  border: `1px solid ${C.border}`,
                  borderRadius: 6,
                  overflowX: "auto",
                }}
              >
                <DiffViewer diff={incident.diff} />
              </div>
            </div>
          )}

          {incident.pr_error && canRetryPr && (
            <div
              style={{
                ...mono,
                fontSize: 11,
                color: C.amber,
                marginBottom: 10,
                background: C.bg,
                border: `1px solid ${C.amber}30`,
                borderRadius: 6,
                padding: "8px 12px",
              }}
            >
              ⚠ {incident.pr_error}
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
            {isGithub && incident.pr_url && (
              <a
                href={incident.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  ...inter,
                  padding: "7px 18px",
                  borderRadius: 7,
                  border: `1px solid ${C.github}40`,
                  background: `${C.github}12`,
                  color: C.github,
                  fontSize: 12,
                  fontWeight: 600,
                  textDecoration: "none",
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

            {!isGithub && isActive && incident.diff && (
              <button
                onClick={handleApprove}
                disabled={loading}
                style={primaryBtn(isLowConf ? C.amber : C.green, loading)}
              >
                {loading ? "Applying…" : isLowConf ? "Force Apply (low confidence) →" : "Apply Fix →"}
              </button>
            )}

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
            <div
              style={{
                ...mono,
                fontSize: 11,
                color: C.red,
                marginTop: 10,
                background: C.bg,
                border: `1px solid ${C.red}30`,
                borderRadius: 6,
                padding: "8px 12px",
              }}
            >
              ✕ {actionError}
            </div>
          )}
        </div>
        </>
      )}
    </div>
  );
}
