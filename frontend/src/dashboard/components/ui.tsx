"use client";

import type { ReactNode } from "react";
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
      className="corner-brackets"
      style={{
        background: C.bg3,
        border: `1px solid ${C.border}`,
        borderRadius: 12,
        overflow: "hidden",
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

export function EmptyState({ label, hint }: { label: string; hint?: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: 220,
        gap: 12,
        padding: 24,
      }}
    >
      <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 32, color: C.dim, opacity: 0.5 }}>⌬</div>
      <span style={{ ...mono, fontSize: 11, color: C.dim }}>{label}</span>
      {hint && (
        <a href="/settings" style={{ ...mono, fontSize: 10, color: C.github, textDecoration: "none", marginTop: 8 }}>
          {hint}
        </a>
      )}
    </div>
  );
}
