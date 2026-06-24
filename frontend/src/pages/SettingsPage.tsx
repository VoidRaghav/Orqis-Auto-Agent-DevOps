"use client";

import { useCallback, useEffect, useState } from "react";
import type { GithubConnectInfo, IdeSetupInfo, WorkspaceSettings } from "@/lib/types";
import SectionLabel from "@/components/ui/SectionLabel";
import TerminalPanel from "@/components/ui/TerminalPanel";
import { colors, mono, inter } from "@/lib/tokens";

import { API_URL } from "@/lib/env";

const C = {
  green: colors.green,
  amber: colors.amber,
  red: colors.red,
  blue: colors.github,
  github: colors.github,
  dim: colors.dim,
  bg: colors.bg,
  bg2: colors.bg2,
  border: colors.border,
};

const ADMIN_TOKEN_KEY = "orqis_admin_token";

export default function SettingsPage() {
  const [github, setGithub] = useState<GithubConnectInfo | null>(null);
  const [ideSetup, setIdeSetup] = useState<IdeSetupInfo | null>(null);
  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [adminToken, setAdminToken] = useState("");
  const [mapRows, setMapRows] = useState<{ source: string; repo: string }[]>([]);
  const [mcpCopied, setMcpCopied] = useState(false);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAdminToken(localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
  }, []);

  const load = useCallback(async () => {
    try {
      const [g, s, ide] = await Promise.all([
        fetch(`${API_URL}/integrations/github/connect`).then((r) => r.json()),
        fetch(`${API_URL}/settings`).then((r) => r.json()),
        fetch(`${API_URL}/integrations/ide-setup`).then((r) => r.json()),
      ]);
      setGithub(g);
      setSettings(s);
      setIdeSetup(ide);
      setMapRows(
        Object.entries(s.source_repo_map ?? {}).map(([source, repo]) => ({
          source,
          repo: repo as string,
        }))
      );
    } catch {
      setStatus({ kind: "err", msg: "Could not reach the Orqis backend." });
    }
  }, []);

  useEffect(() => {
    load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("github") === "connected") {
      setStatus({ kind: "ok", msg: "GitHub connected — repos and account will appear shortly." });
      window.history.replaceState({}, "", "/settings");
      // Webhook may arrive after redirect; poll once for account_login.
      setTimeout(load, 2000);
    }
  }, [load]);

  function rowsToMap(rows: { source: string; repo: string }[]): Record<string, string> {
    const out: Record<string, string> = {};
    for (const { source, repo } of rows) {
      const s = source.trim();
      if (s && repo) out[s] = repo;
    }
    return out;
  }

  async function save() {
    if (!settings) return;
    setSaving(true);
    setStatus(null);
    localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    try {
      const body = {
        source_repo_map: rowsToMap(mapRows),
        default_repo: settings.default_repo,
        default_branch: settings.default_branch,
        hot_reload_webhook_url: settings.hot_reload_webhook_url,
        auto_merge_enabled: settings.auto_merge_enabled,
        pr_low_confidence: settings.pr_low_confidence,
      };
      const r = await fetch(`${API_URL}/settings`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(adminToken ? { "X-Orqis-Admin-Token": adminToken } : {}),
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        setStatus({ kind: "err", msg: await r.text() });
      } else {
        setStatus({ kind: "ok", msg: "Settings saved." });
        await load();
      }
    } catch (e) {
      setStatus({ kind: "err", msg: String(e) });
    } finally {
      setSaving(false);
    }
  }

  async function copyMcpConfig() {
    if (!ideSetup) return;
    const block = ideSetup.configs.cursor_windsurf_claude_project as {
      mcpServers?: Record<string, { command: string; args: string[]; env?: Record<string, string> }>;
    };
    const server = block?.mcpServers?.orqis;
    if (!server) return;
    const payload = {
      mcpServers: {
        orqis: {
          ...server,
          env: {
            ...server.env,
            ORQIS_ADMIN_TOKEN: adminToken || server.env?.ORQIS_ADMIN_TOKEN || "",
          },
        },
      },
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setMcpCopied(true);
      setTimeout(() => setMcpCopied(false), 2000);
    } catch {
      setStatus({ kind: "err", msg: "Could not copy — select the JSON below manually." });
    }
  }

  const grantedRepos = github?.repos ?? [];
  const githubConnected = !!github?.connected;

  return (
    <div className="terminal-grid" style={{ ...inter, background: C.bg, color: "#ddd", minHeight: "100vh", padding: "48px 24px" }}>
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <a href="/dashboard" style={{ ...mono, fontSize: 11, color: C.dim, textDecoration: "none" }}>
          ← back to mission control
        </a>
        <SectionLabel center={false}>Settings</SectionLabel>
        <h1 style={{ ...inter, fontSize: 26, fontWeight: 700, margin: "8px 0 4px" }}>Workspace config</h1>
        <p style={{ color: "#888", fontSize: 13, marginBottom: 32 }}>
          Connect GitHub so Orqis can open reviewable fix PRs. Orqis never writes to your default branch.
        </p>

        {/* GitHub connection */}
        <Section title="GitHub" accent={C.github}>
          {!github?.configured && (
            <Note color={C.amber}>
              The GitHub App isn&apos;t configured on this backend. Set GITHUB_APP_ID, GITHUB_APP_SLUG,
              GITHUB_APP_PRIVATE_KEY and GITHUB_WEBHOOK_SECRET, then restart.
            </Note>
          )}
          {github?.connected ? (
            <div style={{ ...mono, fontSize: 13, color: C.green }}>
              ✓ Connected{github.account_login ? ` as ${github.account_login}` : ""} ·{" "}
              {github.repos.length} repo{github.repos.length === 1 ? "" : "s"} granted
            </div>
          ) : (
            github?.configured && (
              <a href={github.install_url} style={btn(C.blue)}>
                Connect GitHub →
              </a>
            )
          )}
          {github?.repos?.length ? (
            <ul style={{ ...mono, fontSize: 12, color: "#888", marginTop: 12, paddingLeft: 18 }}>
              {github.repos.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : null}
        </Section>

        {/* IDE / MCP setup — same server for every editor */}
        <Section title="IDE & MCP" accent={C.green}>
          <p style={{ color: "#888", fontSize: 12, marginBottom: 12, lineHeight: 1.5 }}>
            Orqis uses one stdio MCP server for every IDE. Add it once, or use{" "}
            <strong style={{ color: "#aaa", fontWeight: 500 }}>Copy for AI assistant</strong> on the
            dashboard to paste a fix prompt into any chat (no MCP required).
          </p>
          {ideSetup && (
            <>
              <p style={{ ...mono, fontSize: 11, color: C.dim, marginBottom: 8 }}>
                Command: <code style={{ color: "#aaa" }}>{ideSetup.mcp_command}</code> · backend{" "}
                <code style={{ color: "#aaa" }}>{ideSetup.backend_url}</code>
              </p>
              <button type="button" onClick={copyMcpConfig} style={{ ...btn(C.blue), marginBottom: 14 }}>
                {mcpCopied ? "Copied .mcp.json snippet" : "Copy .mcp.json snippet"}
              </button>
              <ul style={{ ...mono, fontSize: 11, color: "#888", margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                {ideSetup.ides.map((row) => (
                  <li key={row.name}>
                    <span style={{ color: "#bbb" }}>{row.name}</span> — {row.config}
                  </li>
                ))}
              </ul>
              {adminToken && (
                <Note color={C.green}>
                  Admin token is saved in this browser — the copied MCP config will include it in{" "}
                  <code>env.ORQIS_ADMIN_TOKEN</code> so approve/dismiss/PR tools work from your IDE.
                </Note>
              )}
            </>
          )}
        </Section>

        {settings && (
          <>
            {/* repository routing — choose from repos you actually granted */}
            <Section title="Repositories" accent={C.github}>
              {!githubConnected ? (
                <Note color={C.amber}>
                  Connect GitHub above to choose which repositories Orqis can open fix PRs against.
                </Note>
              ) : grantedRepos.length === 0 ? (
                <Note color={C.amber}>
                  No repositories were granted to the Orqis app. Open the GitHub App settings and
                  grant access to at least one repo, then reload.
                </Note>
              ) : (
                <>
                  <p style={{ color: "#888", fontSize: 12, marginBottom: 10 }}>
                    Default repository — where Orqis opens fix PRs for any log{" "}
                    <code>source</code> without a specific mapping below.
                  </p>
                  <RepoSelect
                    repos={grantedRepos}
                    value={settings.default_repo}
                    placeholder={
                      grantedRepos.length === 1 ? grantedRepos[0] : "Select a repository…"
                    }
                    onChange={(repo) => setSettings({ ...settings, default_repo: repo })}
                  />

                  <div style={{ borderTop: `1px solid ${C.border}`, margin: "18px 0 14px" }} />

                  <p style={{ color: "#888", fontSize: 12, marginBottom: 10 }}>
                    Per-source routing (optional) — send a specific log <code>source</code> to a
                    specific repo. Useful when one Orqis backend watches several services.
                  </p>

                  {mapRows.length === 0 && (
                    <p style={{ ...mono, fontSize: 11, color: C.dim, marginBottom: 10 }}>
                      No source mappings — everything uses the default repository.
                    </p>
                  )}

                  {mapRows.map((row, i) => (
                    <div
                      key={i}
                      style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}
                    >
                      <input
                        value={row.source}
                        onChange={(e) => {
                          const next = [...mapRows];
                          next[i] = { ...next[i], source: e.target.value };
                          setMapRows(next);
                        }}
                        style={{ ...input(false), flex: 1 }}
                        placeholder="log source (e.g. shop-api)"
                        spellCheck={false}
                      />
                      <span style={{ color: C.dim, fontSize: 12 }}>→</span>
                      <div style={{ flex: 1 }}>
                        <RepoSelect
                          repos={grantedRepos}
                          value={row.repo}
                          placeholder="Select repo…"
                          onChange={(repo) => {
                            const next = [...mapRows];
                            next[i] = { ...next[i], repo };
                            setMapRows(next);
                          }}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => setMapRows(mapRows.filter((_, n) => n !== i))}
                        title="Remove mapping"
                        style={{
                          ...mono, fontSize: 14, lineHeight: 1, color: C.dim,
                          background: "transparent", border: `1px solid ${C.border}`,
                          borderRadius: 6, padding: "6px 10px", cursor: "pointer",
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}

                  <button
                    type="button"
                    onClick={() => setMapRows([...mapRows, { source: "", repo: "" }])}
                    style={{
                      ...mono, fontSize: 12, color: C.blue, background: "transparent",
                      border: `1px solid ${C.blue}40`, borderRadius: 6,
                      padding: "6px 12px", cursor: "pointer", marginTop: 4,
                    }}
                  >
                    + Add source mapping
                  </button>
                </>
              )}
            </Section>

            {/* hot reload */}
            <Section title="Hot-reload callback" accent={C.amber}>
              <p style={{ color: "#888", fontSize: 12, marginBottom: 8 }}>
                Optional HTTPS URL Orqis POSTs to (HMAC-signed) after a fix PR merges, so your app can pull
                and reload. Must be public HTTPS — internal addresses are rejected.
              </p>
              <input
                value={settings.hot_reload_webhook_url}
                onChange={(e) => setSettings({ ...settings, hot_reload_webhook_url: e.target.value })}
                style={input(false)}
                placeholder="https://my-app.example.com/orqis/reload"
              />
              <label style={row}>
                <span style={{ ...mono, fontSize: 12, color: "#aaa" }}>Default branch</span>
                <input
                  value={settings.default_branch}
                  onChange={(e) => setSettings({ ...settings, default_branch: e.target.value })}
                  style={{ ...input(false), width: 160 }}
                />
              </label>
            </Section>

            {/* toggles */}
            <Section title="Automation" accent={C.amber}>
              <Toggle
                label="Open PRs for low-confidence fixes"
                desc="By default only high-confidence patches auto-open a PR."
                checked={settings.pr_low_confidence}
                onChange={(v) => setSettings({ ...settings, pr_low_confidence: v })}
              />
              <Toggle
                label="Auto-merge (dangerous)"
                desc="Only merges deterministic, config-only fixes at full validation. Never source code."
                checked={settings.auto_merge_enabled}
                onChange={(v) => setSettings({ ...settings, auto_merge_enabled: v })}
                danger
              />
            </Section>

            {/* admin token + save */}
            <Section title="Admin" accent={C.dim}>
              <p style={{ color: "#888", fontSize: 12, marginBottom: 8 }}>
                Settings changes require the admin token (ORQIS_ADMIN_TOKEN) when set on the backend.
                Stored locally in this browser only.
              </p>
              <input
                value={adminToken}
                onChange={(e) => setAdminToken(e.target.value)}
                type="password"
                style={input(false)}
                placeholder="admin token"
              />
            </Section>

            {status && (
              <Note color={status.kind === "ok" ? C.green : C.red}>{status.msg}</Note>
            )}

            <button onClick={save} disabled={saving} style={{ ...btn(C.green), marginTop: 8 }}>
              {saving ? "Saving…" : "Save settings"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  accent,
}: {
  title: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <TerminalPanel label={title} accent={accent ?? C.github} style={{ marginBottom: 18 }}>
      <div style={{ padding: "16px 18px" }}>{children}</div>
    </TerminalPanel>
  );
}

function RepoSelect({
  repos,
  value,
  placeholder,
  onChange,
}: {
  repos: string[];
  value: string;
  placeholder: string;
  onChange: (repo: string) => void;
}) {
  return (
    <select
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      style={{
        ...mono,
        width: "100%",
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderRadius: 6,
        color: value ? "#ddd" : "#666",
        fontSize: 12,
        padding: "9px 11px",
        outline: "none",
        cursor: "pointer",
      }}
    >
      <option value="">{placeholder}</option>
      {repos.map((r) => (
        <option key={r} value={r} style={{ color: "#ddd", background: C.bg }}>
          {r}
        </option>
      ))}
    </select>
  );
}

function Note({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        ...mono,
        fontSize: 12,
        color,
        background: `${color}10`,
        border: `1px solid ${color}30`,
        borderRadius: 6,
        padding: "10px 12px",
        marginBottom: 12,
        lineHeight: 1.5,
      }}
    >
      {children}
    </div>
  );
}

function Toggle({
  label,
  desc,
  checked,
  onChange,
  danger,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  danger?: boolean;
}) {
  const accent = danger ? C.red : C.green;
  return (
    <label style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 14, cursor: "pointer" }}>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        style={{
          width: 38,
          height: 22,
          borderRadius: 11,
          border: `1px solid ${checked ? accent : C.border}`,
          background: checked ? `${accent}30` : "transparent",
          position: "relative",
          flexShrink: 0,
          cursor: "pointer",
          transition: "all 0.15s",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? 18 : 2,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: checked ? accent : C.dim,
            transition: "all 0.15s",
          }}
        />
      </button>
      <div>
        <div style={{ ...inter, fontSize: 13, color: "#ddd" }}>{label}</div>
        <div style={{ ...inter, fontSize: 11, color: "#777" }}>{desc}</div>
      </div>
    </label>
  );
}

const btn = (color: string): React.CSSProperties => ({
  ...inter,
  display: "inline-block",
  padding: "9px 20px",
  borderRadius: 8,
  border: `1px solid ${color}40`,
  background: `${color}14`,
  color,
  fontSize: 13,
  fontWeight: 600,
  textDecoration: "none",
  cursor: "pointer",
});

const input = (multiline: boolean): React.CSSProperties => ({
  ...mono,
  width: "100%",
  background: C.bg,
  border: `1px solid ${C.border}`,
  borderRadius: 6,
  color: "#ddd",
  fontSize: 12,
  padding: "9px 11px",
  resize: multiline ? ("vertical" as const) : undefined,
  outline: "none",
});

const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  marginTop: 12,
};
