/** Live Incident Simulator — scroll chapters (Carbon Brutalist) */

export type ChapterId =
  | "ops"
  | "detect"
  | "burn"
  | "patch"
  | "ship"
  | "audit"
  | "cta";

export type Chapter = {
  id: ChapterId;
  stamp: string;
  label: string;
  headline: string;
  lines: string[];
  accent: "muted" | "amber" | "red" | "green" | "white";
  metric?: { k: string; v: string };
};

export const INCIDENT_CHAPTERS: Chapter[] = [
  {
    id: "ops",
    stamp: "04:11:58",
    label: "NORMAL",
    headline: "refund-agent · production",
    lines: [
      "orqis.watch() · 3 agents instrumented",
      "last error: none · spend $0.02/min",
      "github: connected · default branch protected",
    ],
    accent: "muted",
  },
  {
    id: "detect",
    stamp: "04:12:00",
    label: "RUNAWAY_LOOP",
    headline: "Loop detected.",
    lines: [
      "check_order_status() ×8 in 30s",
      "refund_agent.py:21 · no exit condition",
      "incident opened · RCA < 900ms",
    ],
    accent: "amber",
    metric: { k: "error class", v: "RUNAWAY_LOOP" },
  },
  {
    id: "burn",
    stamp: "04:12:04",
    label: "BURN",
    headline: "$847/hr projected.",
    lines: [
      "23 API calls in 4.2s · $0.10 spent",
      "rate limit approaching · no kill switch",
      "orqis: circuit_break armed",
    ],
    accent: "red",
    metric: { k: "burn rate", v: "$0.55/s" },
  },
  {
    id: "patch",
    stamp: "04:12:05",
    label: "PATCH",
    headline: "Fix validated.",
    lines: [
      "+ if _attempts >= 5: return escalate()",
      "deterministic guard · confidence 94/100",
      "diff verified · ready to ship",
    ],
    accent: "white",
    metric: { k: "confidence", v: "94/100" },
  },
  {
    id: "ship",
    stamp: "04:12:08",
    label: "PR #1",
    headline: "Branch opened.",
    lines: [
      "orqis/fix-runaway-loop → main",
      "never writes to default branch",
      "review on GitHub · or apply locally",
    ],
    accent: "green",
    metric: { k: "path", v: "GitHub PR · local apply" },
  },
  {
    id: "audit",
    stamp: "04:12:09",
    label: "CHANGES",
    headline: "Logged to disk.",
    lines: [
      "fix_applied · written to refund_agent.py",
      "pr_opened · #1 · Siddarthb07/orqis-e2e-test",
      "full audit trail · expand diff inline",
    ],
    accent: "green",
  },
  {
    id: "cta",
    stamp: "—",
    label: "YOUR TURN",
    headline: "Connect GitHub.",
    lines: [
      "$ connect github --repo=*",
      "Pay for incidents prevented, not seats.",
      "Free local mode · Pro PR-first · Team multi-repo",
    ],
    accent: "white",
  },
];

export const PRICING_ROWS = [
  { tier: "Free", price: "$0", note: "local patch to disk", highlight: false },
  { tier: "Pro", price: "$20/mo", note: "GitHub PR-first · CHANGES log", highlight: true },
  { tier: "Team", price: "$79/mo", note: "multi-repo · shared history", highlight: false },
];
