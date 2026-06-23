"use client";

type Props = {
  opacity?: number;
  className?: string;
};

/** Subtle scanline overlay for mission-control sections. */
export default function ScanlineOverlay({ opacity = 0.04, className = "" }: Props) {
  return (
    <div
      className={`scanline ${className}`}
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        opacity,
        zIndex: 0,
      }}
      aria-hidden
    />
  );
}
