"use client";

import { colors, fonts } from "@/lib/tokens";

type Props = {
  children: React.ReactNode;
  id?: string;
  center?: boolean;
};

export default function SectionLabel({ children, id, center = true }: Props) {
  return (
    <span
      id={id}
      style={{
        fontFamily: fonts.mono,
        fontSize: 11,
        letterSpacing: "0.2em",
        color: colors.green,
        textTransform: "uppercase",
        display: "block",
        textAlign: center ? "center" : "left",
      }}
    >
      ◆ {children}
    </span>
  );
}
