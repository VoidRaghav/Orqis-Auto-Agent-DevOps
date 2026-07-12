import { Navigate, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { API_URL, MULTI_TENANT } from "@/lib/env";

export default function AuthGuard() {
  const [status, setStatus] = useState<"loading" | "ok" | "denied">("loading");

  useEffect(() => {
    if (!MULTI_TENANT) {
      setStatus("ok");
      return;
    }
    fetch(`${API_URL}/auth/me`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setStatus(d.authenticated ? "ok" : "denied"))
      .catch(() => setStatus("denied"));
  }, []);

  if (!MULTI_TENANT) return <Outlet />;
  if (status === "loading") {
    return (
      <div className="dashboard-page" style={{ padding: 48, textAlign: "center", color: "#888" }}>
        Signing in…
      </div>
    );
  }
  if (status === "denied") return <Navigate to="/login" replace />;
  return <Outlet />;
}
