"use client";

import { useEffect, useRef } from "react";
import MetaLabel from "@/components/ui/MetaLabel";
import { registerPanel, unregisterPanel } from "@/lib/panel-registry";

type Props = {
  id: string;
  section: string;
  label: string;
  status: string;
  detail: string;
  accent: string;
  top?: string;
  right?: string;
  bottom?: string;
  className?: string;
  style?: React.CSSProperties;
  priority?: number;
};

export default function FloatingOpsPanel({
  id,
  section,
  label,
  status,
  detail,
  accent,
  top,
  right,
  bottom,
  className = "",
  style,
  priority = 0.85,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    registerPanel({ id, section, el, accent, priority });
    return () => unregisterPanel(id);
  }, [id, section, accent, priority]);

  return (
    <div
      ref={ref}
      className={`floating-ops-panel glass corner-brackets animate-float ${className}`}
      style={{
        top,
        right,
        bottom,
        borderColor: `${accent}44`,
        ...style,
      }}
      aria-hidden
    >
      <MetaLabel accent="#333333" style={{ display: "block", marginBottom: 6 }}>
        ({label})
      </MetaLabel>
      <div className="hero-card-row">
        <span style={{ color: accent }}>{status}</span>
        <span>{detail}</span>
      </div>
    </div>
  );
}
