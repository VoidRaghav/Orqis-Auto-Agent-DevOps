"use client";

import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { C } from "../constants";
import { mono } from "../shared";

export function LiveDot({ color = C.green }: { color?: string }) {
  return (
    <span
      className="pulse-slow"
      style={{
        display: "inline-block",
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: color,
      }}
    />
  );
}

export function Panel({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      className="corner-brackets ops-panel"
      style={{
        background: "rgba(14, 24, 21, 0.55)",
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        overflow: "hidden",
        backdropFilter: "blur(14px) saturate(1.15)",
        boxShadow: "inset 0 1px 0 rgba(94, 207, 184, 0.06)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function PanelHeader({ label, right }: { label: string; right?: ReactNode }) {
  return (
    <div
      style={{
        padding: "10px 16px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: C.bg2,
        borderLeft: `2px solid ${C.green}`,
      }}
    >
      <span style={{ ...mono, fontSize: 10, color: C.dim, letterSpacing: "0.1em", textTransform: "uppercase" }}>
        {label}
      </span>
      {right}
    </div>
  );
}

export function EmptyState({
  label,
  hint,
  hero,
}: {
  label: string;
  hint?: string;
  hero?: boolean;
}) {
  if (hero) {
    return (
      <div className="dashboard-onboard">
        <div className="dashboard-onboard-badge">Mission control</div>
        <h2 className="dashboard-onboard-title">Watching for incidents</h2>
        <p className="dashboard-onboard-sub">{label}</p>

        <div className="dashboard-onboard-steps">
          <div className="dashboard-onboard-step">
            <span className="dashboard-onboard-step-n">1</span>
            <span>Instrument your app</span>
          </div>
          <div className="dashboard-onboard-step">
            <span className="dashboard-onboard-step-n">2</span>
            <span>Connect GitHub</span>
          </div>
          <div className="dashboard-onboard-step">
            <span className="dashboard-onboard-step-n">3</span>
            <span>Review auto-fix PRs</span>
          </div>
        </div>

        <div className="dashboard-onboard-code">
          <div>
            <span className="c-keyword">import</span> <span className="c-name">orqis</span>
          </div>
          <div>
            <span className="c-name">orqis</span>
            <span className="c-fn">.init()</span>
          </div>
        </div>

        {hint && (
          <Link to="/settings" className="dashboard-onboard-cta">
            {hint}
          </Link>
        )}
      </div>
    );
  }

  return (
    <div className="dashboard-empty-state">
      <div className="dashboard-empty-visual" aria-hidden>
        <span className="dashboard-empty-ring dashboard-empty-ring-outer" />
        <span className="dashboard-empty-ring dashboard-empty-ring-mid" />
        <span className="dashboard-empty-ring dashboard-empty-ring-inner" />
        <span className="dashboard-empty-core">◇</span>
      </div>
      <p className="dashboard-empty-label">{label}</p>
      {hint && (
        <Link to="/settings" className="dashboard-empty-hint">
          {hint}
        </Link>
      )}
    </div>
  );
}
