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

export function SectionMeta({
  index,
  total = "05",
  tag,
}: {
  index: string;
  total?: string;
  tag?: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
      {tag && <MetaLabel accent={colors.glow}>{tag}</MetaLabel>}
      <MetaLabel accent={colors.dimmer}>
        [{index} / {total}]
      </MetaLabel>
    </div>
  );
}
