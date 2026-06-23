"use client";

import type { Incident } from "@/lib/types";
import { C, ACTIVE_STATUSES, HEALED_STATUSES } from "../constants";
import { inter, mono } from "../shared";
import { LiveDot } from "./ui";

export default function HealthHero({
  incidents,
  connected,
  hasChanges,
  onViewIssues,
}: {
  incidents: Incident[];
  connected: boolean;
  hasChanges: boolean;
  onViewIssues: () => void;
}) {
  const hasData = incidents.length > 0 || hasChanges;
  const prReady = incidents.filter((i) => i.status === "pr_open").length;
  const prUrl = incidents.find((i) => i.pr_url)?.pr_url;
  const needsAttention = incidents.filter(
    (i) => i.status === "pr_failed" || i.status === "patch_stale",
  ).length;
  const needsYou = incidents.filter(
    (i) =>
      i.status === "patched" ||
      i.status === "low_confidence" ||
      i.status === "pr_open" ||
      i.status === "pr_failed" ||
      i.status === "patch_stale",
  ).length;
  const fixing = incidents.filter((i) => i.status === "open" || i.status === "patching").length;
  const healed = incidents.filter((i) => HEALED_STATUSES.has(i.status)).length;

  let tone: string, title: string, sub: string;
  let action: React.ReactNode = null;

  if (!connected && !hasData) {
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
    action = prUrl ? (
      <a
        href={prUrl}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          ...inter,
          padding: "11px 22px",
          borderRadius: 9,
          border: `1px solid ${C.github}55`,
          background: `${C.github}14`,
          color: C.github,
          fontSize: 13,
          fontWeight: 600,
          textDecoration: "none",
        }}
      >
        Review PR →
      </a>
    ) : (
      <button
        type="button"
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
    );
  } else if (fixing > 0) {
    tone = C.blue;
    title = fixing === 1 ? "Looking into 1 problem" : `Looking into ${fixing} problems`;
    sub = "Orqis spotted an error and is figuring out the fix right now.";
  } else {
    tone = C.green;
    title = "Everything's running smoothly";
    sub = connected
      ? "No errors right now. Orqis is watching your app in the background."
      : "Loaded from server — live stream reconnecting.";
  }

  return (
    <div
      className="scanline"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 20,
        padding: "20px 24px",
        borderBottom: `1px solid ${C.border}`,
        background: `linear-gradient(90deg, ${tone}0c 0%, transparent 60%)`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 10,
            background: tone + "1a",
            border: `1px solid ${tone}40`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            fontFamily: mono.fontFamily,
            color: tone,
            fontSize: 20,
          }}
        >
          [
        </div>
        <div>
          <div
            style={{
              fontFamily: "'Anton', sans-serif",
              fontSize: 24,
              color: C.white,
              letterSpacing: "0.01em",
              lineHeight: 1.1,
            }}
          >
            {title}
          </div>
          <div style={{ ...inter, fontSize: 13, color: C.dim, marginTop: 4 }}>{sub}</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 24, flexShrink: 0 }}>
        {healed > 0 && (
          <div style={{ textAlign: "right" }}>
            <div style={{ fontFamily: "'Anton', sans-serif", fontSize: 26, color: C.green, lineHeight: 1 }}>
              {healed}
            </div>
            <div style={{ ...inter, fontSize: 11, color: C.dim }}>healed</div>
          </div>
        )}
        {action}
      </div>
    </div>
  );
}
