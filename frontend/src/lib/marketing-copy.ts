/** Centralized landing copy — Nebula redesign */

export const boot = {
  command: "$ orqis init --watch production",
  lines: ["scanning agents...", "loop guard armed", "github bridge ready", "CONNECTED"],
};

export const hero = {
  badge: "Mission control · online",
  lines: ["Agents break in prod.", "Orqis ships the fix."],
  sub: "Runaway loops. Stack traces. One reviewable PR — or a local patch in seconds.",
  ctaPrimary: { label: "Connect GitHub →", href: "/settings" },
  ctaSecondary: { label: "Open mission control ↗", href: "/dashboard" },
  telemetry: [
    { val: "<1s", label: "detect", accent: "heal" as const },
    { val: "Loop", label: "guard", accent: "amber" as const },
    { val: "PR", label: "first", accent: "cyan" as const },
    { val: "Any", label: "IDE", accent: "text" as const },
  ],
  rings: [
    { label: "refund-agent", status: "RUNAWAY_LOOP", detail: "patch ready" },
    { label: "orqis/fix-loop", status: "PR #1", detail: "review branch" },
    { label: "CHANGES", status: "fix_applied", detail: "on disk" },
  ],
};

export const signalStrip = {
  prefix: "LIVE",
  messages: [
    "RUNAWAY_LOOP detected · refund_agent.py:21",
    "patch validated · confidence 94/100",
    "PR #1 opened · orqis/fix-runaway-loop → main",
    "CHANGES · fix_applied locally · written to disk",
  ],
};

export const incidentFilm = [
  {
    id: "blind",
    stamp: "04:12 AM",
    headline: "You're blind.",
    sub: "Raw stack traces. No file. No line. No kill switch.",
    metric: { label: "time to root cause", value: "hours" },
    accent: "danger" as const,
  },
  {
    id: "burn",
    stamp: "04:12:04",
    headline: "$847/hr burn.",
    sub: "Recursive agent loop — 23 API calls in 4 seconds.",
    metric: { label: "runaway loop", value: "RUNAWAY_LOOP" },
    accent: "amber" as const,
  },
  {
    id: "patch",
    stamp: "04:12:05",
    headline: "Patch validated.",
    sub: "Deterministic loop guard + diff verification before ship.",
    metric: { label: "confidence", value: "94/100" },
    accent: "cyan" as const,
  },
  {
    id: "ship",
    stamp: "04:12:08",
    headline: "PR #1 ready.",
    sub: "Review on GitHub. Never writes to default branch.",
    metric: { label: "branch", value: "orqis/fix-loop" },
    accent: "heal" as const,
  },
];

export const workflowBento = [
  {
    title: "Detect",
    desc: "Sub-second RCA from logs + tool traces. RUNAWAY_LOOP fingerprinting.",
    span: "large" as const,
    tag: "RUNAWAY_LOOP",
  },
  {
    title: "Patch",
    desc: "Deterministic guards first. LLM fallback when needed.",
    span: "small" as const,
    tag: "diff",
  },
  {
    title: "Review PR",
    desc: "Fix branch → reviewable PR. Default branch untouched.",
    span: "small" as const,
    tag: "PR",
  },
  {
    title: "Apply local",
    desc: "No repo mapped? Approve writes validated diff to disk.",
    span: "small" as const,
    tag: "local",
  },
  {
    title: "Audit",
    desc: "CHANGES log — fix_applied, pr_opened, pr_merged, dismissed.",
    span: "large" as const,
    tag: "CHANGES",
  },
];

export const missionStage = {
  title: "Your console. Always watching.",
  tabs: ["ISSUES & FIXES", "CHANGES", "ACTIVITY"] as const,
};

export const proofWall = {
  title: "Proof, not promises.",
  stats: [
    { label: "loops killed", value: 847, suffix: "" },
    { label: "cost recovered", value: 12400, prefix: "$", suffix: "" },
    { label: "median detect", value: 0.8, suffix: "s" },
    { label: "PRs opened", value: 312, suffix: "" },
  ],
};

export const plans = {
  hook: "Pay for incidents prevented, not seats.",
  tiers: [
    {
      name: "Free",
      price: "$0",
      desc: "Local mode — patch to disk",
      features: ["1 workspace", "Loop detection", "Copy-for-IDE prompts"],
      cta: { label: "Start free", href: "/settings" },
      highlight: false,
    },
    {
      name: "Pro",
      price: "$20/mo",
      desc: "GitHub PR-first for production",
      features: ["GitHub App + fix PRs", "CHANGES audit log", "MCP + any IDE", "30-day retention"],
      cta: { label: "Connect GitHub →", href: "/settings" },
      highlight: true,
    },
    {
      name: "Team",
      price: "$79/mo",
      desc: "Shared ops for multi-agent teams",
      features: ["Everything in Pro", "Multi-repo routing", "Shared incident history"],
      cta: { label: "Contact us", href: "#" },
      highlight: false,
    },
  ],
};

export const launchPad = {
  command: "connect github --repo=*",
  headline: "Ship fixes on branches.",
  sub: "Connect GitHub. Orqis detects, patches, and opens reviewable PRs — or applies locally in dev.",
  cta: { label: "Connect GitHub →", href: "/settings" },
};

export const nav = {
  links: [
    { label: "Story", href: "#story" },
    { label: "Workflow", href: "#workflow" },
    { label: "Console", href: "#mission-control" },
    { label: "Plans", href: "#pricing" },
  ],
};
