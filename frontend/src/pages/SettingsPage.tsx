"use client";

import { useCallback, useEffect, useState } from "react";
import type { GithubConnectInfo, IdeSetupInfo, WorkspaceSettings } from "@/lib/types";
import DashboardNav from "@/dashboard/components/DashboardNav";
import OpsAmbientLayer from "@/dashboard/components/OpsAmbientLayer";
import { resolveOpsMood } from "@/dashboard/components/ops-ambient";
import { inter } from "@/lib/tokens";
import { MULTI_TENANT } from "@/lib/env";
import {
  apiFetchOpts,
  fetchApiKeys,
  fetchAuditLog,
  fetchGithubConnect,
  fetchIdeSetup,
  fetchInvites,
  fetchMembers,
  fetchSettings,
  rowsToMap,
  fetchWorkspaceSources,
  saveSettings,
  type ApiKeySummary,
  type InviteSummary,
  type MemberSummary,
} from "@/lib/api";
import SettingsGithubWizard from "@/components/settings/SettingsGithubWizard";
import SettingsNotificationsCard from "@/components/settings/SettingsNotificationsCard";
import SettingsTeamCard from "@/components/settings/SettingsTeamCard";
import SettingsApiKeysCard from "@/components/settings/SettingsApiKeysCard";
import SettingsAuditCard from "@/components/settings/SettingsAuditCard";
import SettingsIdeCard from "@/components/settings/SettingsIdeCard";
import SettingsRoutingCard from "@/components/settings/SettingsRoutingCard";
import SettingsDeployCard from "@/components/settings/SettingsDeployCard";
import SettingsAutomationCard from "@/components/settings/SettingsAutomationCard";
import SettingsAdminCard from "@/components/settings/SettingsAdminCard";

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
  const [apiKeys, setApiKeys] = useState<ApiKeySummary[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [auditLog, setAuditLog] = useState<Awaited<ReturnType<typeof fetchAuditLog>>>([]);
  const [members, setMembers] = useState<MemberSummary[]>([]);
  const [pendingInvites, setPendingInvites] = useState<InviteSummary[]>([]);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [recentSources, setRecentSources] = useState<string[]>([]);

  useEffect(() => {
    setAdminToken(localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
  }, []);

  const fetchOpts = useCallback(() => apiFetchOpts(adminToken), [adminToken]);

  const load = useCallback(async () => {
    try {
      const [g, s, ide] = await Promise.all([
        fetchGithubConnect(adminToken),
        fetchSettings(adminToken),
        fetchIdeSetup(),
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
      setRecentSources(await fetchWorkspaceSources(adminToken));
      if (MULTI_TENANT) {
        const [keys, audit, mems, invites] = await Promise.all([
          fetchApiKeys(adminToken),
          fetchAuditLog(adminToken),
          fetchMembers(adminToken),
          fetchInvites(adminToken),
        ]);
        setApiKeys(keys);
        setAuditLog(audit);
        setMembers(mems);
        setPendingInvites(
          invites.map((inv) => ({
            ...inv,
            url: `${window.location.origin}/invite/${inv.token}`,
          })),
        );
      }
    } catch {
      setBackendOk(false);
      setStatus({ kind: "err", msg: "Backend unreachable." });
    }
  }, [adminToken]);

  useEffect(() => {
    load();
    const params = new URLSearchParams(window.location.search);
    if (params.get("github") === "connected") {
      setStatus({ kind: "ok", msg: "GitHub connected." });
      window.history.replaceState({}, "", "/settings");
      setTimeout(load, 2000);
    }
    if (params.get("github") === "app_registered") {
      setStatus({ kind: "ok", msg: "GitHub App registered — install it on your repos next." });
      window.history.replaceState({}, "", "/settings");
      setTimeout(load, 1500);
    }
  }, [load]);

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
        notification_webhook_url: settings.notification_webhook_url ?? "",
        notification_slack_url: settings.notification_slack_url ?? "",
      };
      const r = await saveSettings(body, adminToken);
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
            <SettingsGithubWizard
              github={github}
              fetchOpts={fetchOpts}
              onReload={load}
              onError={(msg) => setStatus({ kind: "err", msg })}
            />

            {MULTI_TENANT && (
              <SettingsTeamCard
                members={members}
                pendingInvites={pendingInvites}
                inviteUrl={inviteUrl}
                fetchOpts={fetchOpts}
                onInviteCreated={setInviteUrl}
                onReload={load}
                onError={(msg) => setStatus({ kind: "err", msg })}
              />
            )}

            {MULTI_TENANT && (
              <SettingsApiKeysCard
                apiKeys={apiKeys}
                newKey={newKey}
                fetchOpts={fetchOpts}
                onNewKey={setNewKey}
                onReload={load}
              />
            )}

            {MULTI_TENANT && <SettingsAuditCard auditLog={auditLog} />}

            <SettingsIdeCard
              ideSetup={ideSetup}
              adminToken={adminToken}
              newKey={newKey}
              mcpCopied={mcpCopied}
              onCopyMcp={copyMcpConfig}
            />

            {settings && (
              <SettingsNotificationsCard
                settings={settings}
                onSettingsChange={setSettings}
                fetchOpts={fetchOpts}
                onTestResult={(ok, msg) =>
                  setStatus({ kind: ok ? "ok" : "err", msg })
                }
              />
            )}

            {settings && (
              <>
                <SettingsRoutingCard
                  settings={settings}
                  grantedRepos={grantedRepos}
                  githubConnected={githubConnected}
                  mapRows={mapRows}
                  recentSources={recentSources}
                  onSettingsChange={setSettings}
                  onMapRowsChange={setMapRows}
                />
                <SettingsDeployCard settings={settings} onSettingsChange={setSettings} />
                <SettingsAutomationCard settings={settings} onSettingsChange={setSettings} />
                <SettingsAdminCard adminToken={adminToken} onAdminTokenChange={setAdminToken} />
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
