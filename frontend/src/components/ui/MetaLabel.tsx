import type { CSSProperties } from "react";
import { colors, fonts } from "@/lib/tokens";

type Props = {
  children: React.ReactNode;
  style?: CSSProperties;
  accent?: string;
};

export default function MetaLabel({ children, style, accent = colors.muted }: Props) {
  return (
    <span
      className="meta-label"
      style={{
        fontFamily: fonts.mono,
        fontSize: 10,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: accent,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

// Section tag/number chrome removed from the marketing sections — kept as a
// no-op so existing call sites don't need to change.
export function SectionMeta(_props: {
  index?: string;
  total?: string;
  tag?: string;
}) {
  return null;
}
