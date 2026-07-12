"use client";

import { useCallback, useEffect, useState } from "react";
import type { GithubConnectInfo, IdeSetupInfo, WorkspaceAuditEntry, WorkspaceSettings } from "@/lib/types";
import DashboardNav from "@/dashboard/components/DashboardNav";
import OpsAmbientLayer from "@/dashboard/components/OpsAmbientLayer";
import { resolveOpsMood } from "@/dashboard/components/ops-ambient";
import { colors, mono, inter } from "@/lib/tokens";
import { API_URL, MULTI_TENANT } from "@/lib/env";

const C = {
  green: colors.green,
  amber: colors.amber,
  red: colors.red,
  blue: colors.github,
  github: colors.github,
  dim: colors.dim,
  muted: colors.muted,
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
  const [backendOk, setBackendOk] = useState(false);

  useEffect(() => {
    setAdminToken(localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
  }, []);

  const [apiKeys, setApiKeys] = useState<{ id: string; prefix: string; label: string }[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [auditLog, setAuditLog] = useState<WorkspaceAuditEntry[]>([]);
  const [members, setMembers] = useState<{ github_id: number; login: string; role: string }[]>([]);
  const [pendingInvites, setPendingInvites] = useState<{ token: string; url?: string; created_at: string }[]>([]);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);

  const fetchOpts = (): RequestInit => ({
    credentials: MULTI_TENANT ? "include" : "same-origin",
    headers: {
      ...(adminToken ? { "X-Orqis-Admin-Token": adminToken } : {}),
    },
  });

  const load = useCallback(async () => {
    try {
      const opts = fetchOpts();
      const [g, s, ide] = await Promise.all([
        fetch(`${API_URL}/integrations/github/connect`, opts).then((r) => r.json()),
        fetch(`${API_URL}/settings`, opts).then((r) => r.json()),
        fetch(`${API_URL}/integrations/ide-setup`).then((r) => r.json()),
      ]);
      setGithub(g);
      setSettings(s);
      setIdeSetup(ide);
      setMapRows(
        Object.entries(s.source_repo_map ?? {}).map(([source, repo]) => ({
          source,
          repo: repo as string,
        })),
      );
      setBackendOk(true);
      if (MULTI_TENANT) {
        const [keys, audit, mems, invites] = await Promise.all([
          fetch(`${API_URL}/workspace/api-keys`, opts).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API_URL}/workspace/audit?limit=30`, opts).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API_URL}/workspace/members`, opts).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API_URL}/workspace/invites`, opts).then((r) => (r.ok ? r.json() : [])),
        ]);
        setApiKeys(keys);
        setAuditLog(audit);
        setMembers(mems);
        setPendingInvites(
          invites.map((inv: { token: string; created_at: string }) => ({
            ...inv,
            url: `${window.location.origin}/invite/${inv.token}`,
          })),
        );
      }
    } catch {
      setBackendOk(false);
      setStatus({ kind: "err", msg: "Backend unreachable." });
    }
  }, []);

  useEffect(() => {
    load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("github") === "connected") {
      setStatus({ kind: "ok", msg: "GitHub connected." });
      window.history.replaceState({}, "", "/settings");
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
        ...fetchOpts(),
        headers: {
          "Content-Type": "application/json",
          ...(adminToken ? { "X-Orqis-Admin-Token": adminToken } : {}),
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        setStatus({ kind: "err", msg: await r.text() });
      } else {
        setStatus({ kind: "ok", msg: "Saved." });
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
          env: MULTI_TENANT
            ? {
                ...server.env,
                ORQIS_API_KEY: newKey || server.env?.ORQIS_API_KEY || "<workspace-api-key>",
              }
            : {
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
      setStatus({ kind: "err", msg: "Copy failed." });
    }
  }

  const grantedRepos = github?.repos ?? [];
  const githubConnected = !!github?.connected;
  const mood = resolveOpsMood({ connected: backendOk, hasData: !!settings });

  return (
    <div className="settings-page" data-mood={mood} style={{ ...inter }}>
      <OpsAmbientLayer mood={mood} />
      <div className="ops-page-content">
      <DashboardNav connected={backendOk} github={github} />

      <div className="settings-wrap">
        <header className="settings-header">
          <h1 className="settings-title">Settings</h1>
          <p className="settings-lead">GitHub PRs · repo routing · automation</p>
        </header>

        {status && (
          <div className={`settings-banner settings-banner-${status.kind}`}>{status.msg}</div>
        )}

        <div className="settings-grid">
          <Card title="GitHub" accent={C.github}>
            {!github?.configured && (
              <Hint tone="warn">Set GITHUB_APP_* env vars on backend, then restart.</Hint>
            )}
            {github?.connected ? (
              <Row label="Status" value={`Connected · ${github.repos.length} repo${github.repos.length === 1 ? "" : "s"}`} tone={C.green} />
            ) : (
              github?.configured && (
                <a href={github.install_url} className="settings-btn settings-btn-github">
                  Connect GitHub
                </a>
              )
            )}
            {github?.account_login && <Row label="Account" value={github.account_login} />}
            {grantedRepos.length > 0 && (
              <div className="settings-repo-chips">
                {grantedRepos.map((r) => (
                  <span key={r} className="settings-chip">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </Card>

          {MULTI_TENANT && (
            <Card title="Team" accent={C.blue}>
              <Hint>Invite teammates — they sign in with GitHub to join this workspace.</Hint>
              <ul className="settings-ide-list">
                {members.map((m) => (
                  <li key={m.github_id}>
                    <span>
                      {m.login}{" "}
                      <span className="settings-muted">({m.role})</span>
                    </span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="settings-btn settings-btn-ghost"
                onClick={async () => {
                  const r = await fetch(`${API_URL}/workspace/invites`, {
                    method: "POST",
                    ...fetchOpts(),
                  });
                  if (r.ok) {
                    const data = await r.json();
                    setInviteUrl(data.url);
                    await load();
                  } else {
                    setStatus({ kind: "err", msg: await r.text() });
                  }
                }}
              >
                Create invite link
              </button>
              {inviteUrl && (
                <div className="settings-banner settings-banner-ok" style={{ wordBreak: "break-all" }}>
                  Share once: <code>{inviteUrl}</code>
                </div>
              )}
              {pendingInvites.length > 0 && (
                <ul className="settings-ide-list">
                  {pendingInvites.map((inv) => (
                    <li key={inv.token}>
                      <span className="settings-ide-path">{inv.url}</span>
                      <button
                        type="button"
                        className="settings-link-btn"
                        onClick={async () => {
                          await fetch(`${API_URL}/workspace/invites/${inv.token}`, {
                            method: "DELETE",
                            ...fetchOpts(),
                          });
                          await load();
                        }}
                      >
                        Revoke
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {MULTI_TENANT && (
            <Card title="Ingest API keys" accent={C.amber}>
              <Hint>Use in orqis.init(api_key=…) or Authorization: Bearer</Hint>
              {newKey && (
                <div className="settings-banner settings-banner-ok" style={{ wordBreak: "break-all" }}>
                  Copy now — shown once: <code>{newKey}</code>
                </div>
              )}
              <ul className="settings-ide-list">
                {apiKeys.map((k) => (
                  <li key={k.id}>
                    <span>{k.label}</span>
                    <span className="settings-ide-path">{k.prefix}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="settings-btn settings-btn-ghost"
                onClick={async () => {
                  const r = await fetch(`${API_URL}/workspace/api-keys?label=ingest`, {
                    method: "POST",
                    ...fetchOpts(),
                  });
                  if (r.ok) {
                    const data = await r.json();
                    setNewKey(data.key);
                    await load();
                  }
                }}
              >
                Generate key
              </button>
            </Card>
          )}

          {MULTI_TENANT && (
            <Card title="Audit log" accent={C.dim} wide>
              <Hint>Recent workspace write actions (30 days retention)</Hint>
              {auditLog.length === 0 ? (
                <span className="settings-muted">No audit entries yet.</span>
              ) : (
                <ul className="settings-audit-list">
                  {auditLog.map((entry) => (
                    <li key={entry.id} className="settings-audit-row">
                      <span className="settings-audit-time">
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                      <span className="settings-audit-action" style={{ ...mono }}>
                        {entry.action}
                      </span>
                      <span className="settings-audit-detail">
                        {entry.resource_type}
                        {entry.resource_id ? ` · ${entry.resource_id.slice(0, 12)}` : ""}
                        {" · "}
                        {entry.actor}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          <Card title="IDE / MCP" accent={C.green}>
            <Hint>One stdio server · all editors</Hint>
            {ideSetup && (
              <>
                <Row label="Command" value={ideSetup.mcp_command} mono />
                <button type="button" onClick={copyMcpConfig} className="settings-btn settings-btn-ghost">
                  {mcpCopied ? "Copied" : "Copy .mcp.json"}
                </button>
                <ul className="settings-ide-list">
                  {ideSetup.ides.map((row) => (
                    <li key={row.name}>
                      <span>{row.name}</span>
                      <span className="settings-ide-path">{row.config}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          {settings && (
            <>
              <Card title="Repositories" accent={C.github} wide>
                {!githubConnected ? (
                  <Hint tone="warn">Connect GitHub first.</Hint>
                ) : grantedRepos.length === 0 ? (
                  <Hint tone="warn">Grant at least one repo in GitHub App settings.</Hint>
                ) : (
                  <>
                    <Field label="Default repo">
                      <RepoSelect
                        repos={grantedRepos}
                        value={settings.default_repo}
                        placeholder={grantedRepos.length === 1 ? grantedRepos[0] : "Select…"}
                        onChange={(repo) => setSettings({ ...settings, default_repo: repo })}
                      />
                    </Field>

                    <div className="settings-divider" />

                    <Field label="Source → repo (optional)">
                      {mapRows.length === 0 && <span className="settings-muted">Uses default for all sources.</span>}
                      {mapRows.map((row, i) => (
                        <div key={i} className="settings-map-row">
                          <input
                            value={row.source}
                            onChange={(e) => {
                              const next = [...mapRows];
                              next[i] = { ...next[i], source: e.target.value };
                              setMapRows(next);
                            }}
                            className="settings-input"
                            placeholder="source"
                            spellCheck={false}
                          />
                          <span className="settings-arrow">→</span>
                          <RepoSelect
                            repos={grantedRepos}
                            value={row.repo}
                            placeholder="repo"
                            onChange={(repo) => {
                              const next = [...mapRows];
                              next[i] = { ...next[i], repo };
                              setMapRows(next);
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => setMapRows(mapRows.filter((_, n) => n !== i))}
                            className="settings-icon-btn"
                            aria-label="Remove"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => setMapRows([...mapRows, { source: "", repo: "" }])}
                        className="settings-link-btn"
                      >
                        + Add mapping
                      </button>
                    </Field>
                  </>
                )}
              </Card>

              <Card title="Deploy" accent={C.amber}>
                <Field label="Hot-reload URL">
                  <input
                    value={settings.hot_reload_webhook_url}
                    onChange={(e) => setSettings({ ...settings, hot_reload_webhook_url: e.target.value })}
                    className="settings-input"
                    placeholder="https://app.example.com/orqis/reload"
                  />
                </Field>
                <Field label="Default branch">
                  <input
                    value={settings.default_branch}
                    onChange={(e) => setSettings({ ...settings, default_branch: e.target.value })}
                    className="settings-input settings-input-sm"
                  />
                </Field>
              </Card>

              <Card title="Automation" accent={C.amber}>
                <Toggle
                  label="Low-confidence PRs"
                  checked={settings.pr_low_confidence}
                  onChange={(v) => setSettings({ ...settings, pr_low_confidence: v })}
                />
                <Toggle
                  label="Auto-merge (config only)"
                  checked={settings.auto_merge_enabled}
                  onChange={(v) => setSettings({ ...settings, auto_merge_enabled: v })}
                  danger
                />
              </Card>

              <Card title="Admin" accent={C.dim}>
                {MULTI_TENANT ? (
                  <Hint>Hosted multi-tenant uses session + API keys. Admin token is local dev only.</Hint>
                ) : (
                  <>
                    <Field label="Token">
                      <input
                        value={adminToken}
                        onChange={(e) => setAdminToken(e.target.value)}
                        type="password"
                        className="settings-input"
                        placeholder="ORQIS_ADMIN_TOKEN"
                      />
                    </Field>
                    <Hint>Stored in browser only.</Hint>
                  </>
                )}
              </Card>
            </>
          )}
        </div>

        {settings && (
          <div className="settings-footer">
            <button type="button" onClick={save} disabled={saving} className="settings-btn settings-btn-save">
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

function Card({
  title,
  children,
  accent,
  wide,
}: {
  title: string;
  children: React.ReactNode;
  accent?: string;
  wide?: boolean;
}) {
  return (
    <section className={`settings-card corner-brackets${wide ? " settings-card-wide" : ""}`} style={{ borderLeftColor: accent }}>
      <div className="settings-card-head" style={{ borderLeftColor: accent }}>
        <span style={{ ...mono }}>{title}</span>
      </div>
      <div className="settings-card-body">{children}</div>
    </section>
  );
}

function Row({ label, value, tone, mono: isMono }: { label: string; value: string; tone?: string; mono?: boolean }) {
  return (
    <div className="settings-row">
      <span className="settings-row-label">{label}</span>
      <span className="settings-row-value" style={{ color: tone, ...(isMono ? mono : {}) }}>
        {value}
      </span>
    </div>
  );
}

function Hint({ children, tone }: { children: React.ReactNode; tone?: "warn" }) {
  return <p className={`settings-hint${tone === "warn" ? " settings-hint-warn" : ""}`}>{children}</p>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="settings-field">
      <span className="settings-field-label">{label}</span>
      {children}
    </label>
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
    <select value={value || ""} onChange={(e) => onChange(e.target.value)} className="settings-select">
      <option value="">{placeholder}</option>
      {repos.map((r) => (
        <option key={r} value={r}>
          {r}
        </option>
      ))}
    </select>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  danger,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  danger?: boolean;
}) {
  const accent = danger ? C.red : C.green;
  return (
    <label className="settings-toggle">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className="settings-switch"
        style={{
          borderColor: checked ? accent : C.border,
          background: checked ? `${accent}30` : "transparent",
        }}
      >
        <span className="settings-switch-knob" style={{ left: checked ? 18 : 2, background: checked ? accent : C.dim }} />
      </button>
      <span className="settings-toggle-label">{label}</span>
    </label>
  );
}
