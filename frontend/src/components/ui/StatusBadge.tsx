"use client";

import { colors, fonts, statusColors } from "@/lib/tokens";

type Props = {
  status: string;
  size?: "sm" | "md";
  pulse?: boolean;
};

export default function StatusBadge({ status, size = "sm", pulse = false }: Props) {
  const color = statusColors[status] ?? statusColors[status.toLowerCase()] ?? colors.dim;
  const label = status.replace(/_/g, " ").toUpperCase();
  const fontSize = size === "md" ? 11 : 9;
  const pad = size === "md" ? "3px 10px" : "2px 7px";

  return (
    <span
      className={pulse ? "pulse-slow" : undefined}
      style={{
        fontFamily: fonts.mono,
        fontSize,
        padding: pad,
        borderRadius: 4,
        background: color + "18",
        color,
        letterSpacing: "0.06em",
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        whiteSpace: "nowrap",
      }}
    >
      {pulse && (
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: color,
            display: "inline-block",
          }}
        />
      )}
      {label}
    </span>
  );
}
