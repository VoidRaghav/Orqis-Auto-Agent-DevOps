"use client";

import { Link } from "react-router-dom";
import type { GithubConnectInfo } from "@/lib/types";
import { C } from "../constants";
import { mono } from "../shared";
import { LiveDot } from "./ui";

export default function TopBar({
  connected,
  totalCost,
  github,
}: {
  connected: boolean;
  totalCost: number;
  github: GithubConnectInfo | null;
}) {
  return (
    <div
      className="terminal-grid"
      style={{
        height: 54,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        borderBottom: `1px solid ${C.border}`,
        background: C.bg2,
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
          <div
            style={{
              width: 26,
              height: 26,
              borderRadius: 6,
              background: `linear-gradient(135deg, ${C.green} 0%, ${C.white} 100%)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              fontWeight: 700,
              color: "#000",
            }}
          >
            ⌬
          </div>
          <span style={{ fontFamily: "'Anton', sans-serif", fontSize: 16, color: C.white, letterSpacing: "0.03em" }}>
            ORQIS
          </span>
        </Link>
        <span style={{ color: C.border, fontSize: 16 }}>/</span>
        <span style={{ ...mono, fontSize: 12, color: C.dim }}>[production]</span>
        <span className="cursor-blink" style={{ ...mono, fontSize: 12, color: C.green }}>
          _
        </span>
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
            {connected ? "CONNECTED" : "RECONNECTING"}
          </span>
        </div>
        <GithubBadge github={github} />
        <a href="/settings" style={{ ...mono, fontSize: 11, color: C.dim, textDecoration: "none" }}>
          ⚙ Settings
        </a>
      </div>
    </div>
  );
}

function GithubBadge({ github }: { github: GithubConnectInfo | null }) {
  const base: React.CSSProperties = {
    ...mono,
    fontSize: 11,
    textDecoration: "none",
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 10px",
    borderRadius: 7,
    border: `1px solid ${C.border}`,
  };

  if (github?.connected) {
    const repoCount = github.repos.length;
    const label =
      repoCount === 1
        ? github.repos[0]
        : repoCount > 1
          ? `${github.account_login ?? "github"} · ${repoCount} repos`
          : github.account_login ?? "connected";
    return (
      <a
        href="/settings"
        style={{ ...base, color: C.github, borderColor: `${C.github}40`, background: `${C.github}10` }}
      >
        <span style={{ fontSize: 12 }}>⎇</span>
        <span style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {label}
        </span>
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

  return (
    <a href="/settings" style={{ ...base, color: C.dim }}>
      <span style={{ fontSize: 12 }}>⎇</span> Local mode
    </a>
  );
}
