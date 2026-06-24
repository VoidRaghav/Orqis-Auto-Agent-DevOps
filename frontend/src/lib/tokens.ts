import type { CSSProperties } from "react";

/** Loop Autopsy × Organic Field — Awwwards palette */

export const colors = {
  bg: "#050a08",
  bg2: "#0a1210",
  bg3: "#0f1a16",
  surface: "#14221c",
  border: "rgba(245, 240, 232, 0.08)",
  borderStrong: "rgba(245, 240, 232, 0.14)",
  white: "#ffffff",
  ivory: "#f5f0e8",
  phosphor: "#5ecfb8",
  viridian: "#1a3d32",
  dim: "#4a5c54",
  dimmer: "#2a3832",
  muted: "#7a8f84",
  heal: "#3ddc97",
  healDim: "rgba(61, 220, 151, 0.1)",
  green: "#3ddc97",
  greenDim: "rgba(61, 220, 151, 0.1)",
  amber: "#e8a045",
  amberDim: "rgba(232, 160, 69, 0.1)",
  red: "#e85d4a",
  redDim: "rgba(232, 93, 74, 0.1)",
  blue: "#6eb5ff",
  blueDim: "rgba(110, 181, 255, 0.1)",
  glow: "#5ecfb8",
  glowDim: "rgba(94, 207, 184, 0.08)",
  github: "#6eb5ff",
  githubDim: "rgba(110, 181, 255, 0.12)",
} as const;

export const fonts = {
  anton: "'Anton', sans-serif",
  serif: "'Instrument Serif', Georgia, serif",
  mono: "'DM Mono', monospace",
  inter: "'Inter', sans-serif",
} as const;

export const statusColors: Record<string, string> = {
  open: colors.amber,
  patching: colors.blue,
  patched: colors.heal,
  low_confidence: colors.amber,
  approved: colors.heal,
  dismissed: colors.dim,
  pr_open: colors.github,
  pr_failed: colors.red,
  patch_stale: colors.amber,
  resolved: colors.heal,
  RUNAWAY_LOOP: colors.amber,
};

export const mono: CSSProperties = { fontFamily: fonts.mono };
export const inter: CSSProperties = { fontFamily: fonts.inter };
