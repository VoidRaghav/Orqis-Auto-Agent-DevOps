import type { CSSProperties } from "react";
import { C } from "./constants";

export const mono: CSSProperties = { fontFamily: "'DM Mono', monospace" };
export const inter: CSSProperties = { fontFamily: "'Inter', sans-serif" };

export function primaryBtn(color: string, loading: boolean): CSSProperties {
  return {
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
  };
}

export function ghostBtn(loading: boolean): CSSProperties {
  return {
    ...inter,
    padding: "7px 18px",
    borderRadius: 7,
    border: `1px solid ${C.border}`,
    background: "transparent",
    color: C.dim,
    fontSize: 12,
    cursor: loading ? "not-allowed" : "pointer",
    transition: "all 0.15s",
  };
}

export function errorMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // not JSON
  }
  return raw || "Something went wrong. Please try again.";
}

export async function copyToClipboard(text: string): Promise<void> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // fall through
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

export function buildSparkline(events: { timestamp: string; is_error?: boolean }[]) {
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
