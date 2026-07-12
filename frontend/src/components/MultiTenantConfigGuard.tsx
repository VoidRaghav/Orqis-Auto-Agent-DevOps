import { useEffect, useState } from "react";
import { API_URL, MULTI_TENANT } from "@/lib/env";

/**
 * Warn when frontend VITE_MULTI_TENANT disagrees with backend ORQIS_MULTI_TENANT.
 */
export default function MultiTenantConfigGuard() {
  const [mismatch, setMismatch] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && Boolean(d.multi_tenant) !== MULTI_TENANT) {
          setMismatch(true);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!mismatch) return null;

  const frontend = MULTI_TENANT ? "1" : "0";
  const hint = MULTI_TENANT
    ? "Backend has ORQIS_MULTI_TENANT=0 — login and workspace isolation are disabled."
    : "Backend has ORQIS_MULTI_TENANT=1 — set VITE_MULTI_TENANT=1 and rebuild the frontend.";

  return (
    <div
      role="alert"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        padding: "10px 16px",
        background: "#3d1f00",
        borderBottom: "1px solid #f59e0b",
        color: "#fcd34d",
        fontSize: 13,
        textAlign: "center",
      }}
    >
      <strong>Config mismatch:</strong> VITE_MULTI_TENANT={frontend} but backend /health disagrees. {hint}
    </div>
  );
}
