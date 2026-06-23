"use client";

import type { CSSProperties, ReactNode } from "react";
import { colors, fonts, mono } from "@/lib/tokens";

type Props = {
  label?: string;
  right?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
  accent?: string;
  className?: string;
};

export default function TerminalPanel({
  label,
  right,
  children,
  style,
  accent = colors.green,
  className = "",
}: Props) {
  return (
    <div
      className={`corner-brackets terminal-panel ${className}`}
      style={{
        background: colors.bg3,
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        overflow: "hidden",
        position: "relative",
        ...style,
      }}
    >
      {label && (
        <div
          style={{
            padding: "10px 16px",
            borderBottom: `1px solid ${colors.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: colors.bg2,
            borderLeft: `2px solid ${accent}`,
          }}
        >
          <span
            style={{
              ...mono,
              fontSize: 10,
              color: colors.dim,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            {label}
          </span>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function TerminalTitleBar({
  title,
  right,
  live,
}: {
  title: string;
  right?: ReactNode;
  live?: boolean;
}) {
  return (
    <div
      style={{
        background: colors.bg2,
        padding: "12px 20px",
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c, i) => (
          <div
            key={i}
            style={{ width: 11, height: 11, borderRadius: "50%", background: c }}
          />
        ))}
        <span style={{ ...mono, color: colors.dimmer, marginLeft: 10, fontSize: 12 }}>
          {title}
        </span>
      </div>
      {live ? (
        <span
          style={{
            ...mono,
            fontSize: 11,
            color: colors.green,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span
            className="pulse-slow"
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: colors.green,
              display: "inline-block",
            }}
          />
          LIVE
        </span>
      ) : (
        right
      )}
    </div>
  );
}
