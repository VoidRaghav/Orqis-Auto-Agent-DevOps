"use client";

type Props = {
  accent?: string;
  side?: "left" | "full";
};

function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}

/** Soft accent wash — robot + tendrils bleed through staged content. */
export default function FlowSectionOverlay({ accent = "#00e5ff", side = "left" }: Props) {
  const rgb = hexToRgb(accent);

  return (
    <div
      className={`flow-section-overlay flow-section-overlay--${side}`}
      style={{
        background:
          side === "left"
            ? `linear-gradient(90deg, rgba(${rgb}, 0.09) 0%, rgba(${rgb}, 0.02) 42%, transparent 78%)`
            : `radial-gradient(ellipse 80% 80% at 30% 50%, rgba(${rgb}, 0.06) 0%, transparent 70%)`,
      }}
      aria-hidden
    />
  );
}
