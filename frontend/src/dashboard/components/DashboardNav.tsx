import { Link, useLocation } from "react-router-dom";
import MetaLabel from "@/components/ui/MetaLabel";
import { colors, fonts, mono } from "@/lib/tokens";
import type { GithubConnectInfo } from "@/lib/types";

export default function DashboardNav({
  connected,
  totalCost = 0,
  github,
}: {
  connected: boolean;
  totalCost?: number;
  github: GithubConnectInfo | null;
}) {
  const { pathname } = useLocation();

  return (
    <header className="dashboard-nav">
      <Link to="/" className="dashboard-nav-brand">
        <span style={{ fontFamily: fonts.anton, fontSize: 18, color: colors.white, letterSpacing: "0.06em" }}>
          ORQIS
        </span>
      </Link>

      <nav className="dashboard-nav-links">
        <Link to="/dashboard" className={`dashboard-nav-link ${pathname === "/dashboard" ? "is-active" : ""}`}>
          Dashboard
        </Link>
        <Link to="/settings" className={`dashboard-nav-link ${pathname === "/settings" ? "is-active" : ""}`}>
          Settings
        </Link>
        <MetaLabel accent={colors.dimmer}>[production]</MetaLabel>
      </nav>

      <div className="dashboard-nav-status">
        {totalCost > 0 && (
          <span style={{ ...mono, fontSize: 10, color: totalCost > 1 ? colors.amber : colors.green }}>
            ${totalCost.toFixed(4)}
          </span>
        )}
        <span style={{ ...mono, fontSize: 10, color: connected ? colors.green : colors.red, display: "flex", alignItems: "center", gap: 6 }}>
          <span className="pulse-slow" style={{ width: 6, height: 6, borderRadius: "50%", background: connected ? colors.green : colors.red }} />
          {connected ? "LIVE" : "OFFLINE"}
        </span>
        {github?.connected && (
          <Link to="/settings" style={{ ...mono, fontSize: 10, color: colors.github, textDecoration: "none" }}>
            ⎇ {github.account_login ?? "github"}
          </Link>
        )}
      </div>
    </header>
  );
}
