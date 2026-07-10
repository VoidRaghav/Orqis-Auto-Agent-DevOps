"use client";

import type { ReactNode } from "react";
import ScanlineOverlay from "@/components/ui/ScanlineOverlay";
import { TerminalTitleBar } from "@/components/ui/TerminalPanel";

export default function MissionControlShell({
  connected,
  status,
  kpis,
  children,
}: {
  connected: boolean;
  status: ReactNode;
  kpis: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mc-shell corner-brackets">
      <ScanlineOverlay opacity={0.035} />

      <TerminalTitleBar title="orqis — mission control" live={connected} />

      <div className="mc-shell-head">
        <div className="mc-shell-status">{status}</div>
        <div className="mc-shell-kpis">{kpis}</div>
      </div>

      <div className="mc-shell-body">{children}</div>
    </div>
  );
}
