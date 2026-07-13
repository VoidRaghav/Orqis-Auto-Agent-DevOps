"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/env";
import type { GithubConnectInfo, GithubSetupStatus } from "@/lib/types";
import { fetchGithubSetupStatus, startGithubRegister } from "@/lib/api";
import { Card, Hint, Row, settingsColors } from "./SettingsUi";

type Props = {
  github: GithubConnectInfo | null;
  fetchOpts: () => RequestInit;
  onReload: () => Promise<void>;
  onError: (msg: string) => void;
};

const STEPS = [
  { id: "register", label: "Register app" },
  { id: "install", label: "Install on repos" },
  { id: "webhook", label: "Webhook" },
  { id: "ready", label: "Ready" },
] as const;

function stepIndex(status: GithubSetupStatus | null): number {
  if (!status?.app_configured) return 0;
  if (!status.connected) return 1;
  if (!status.webhook_configured || (status.repos_count ?? 0) === 0) return 2;
  return 3;
}

export default function SettingsGithubWizard({ github, fetchOpts, onReload, onError }: Props) {
  const [setup, setSetup] = useState<GithubSetupStatus | null>(null);
  const [registering, setRegistering] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadSetup = useCallback(async () => {
    try {
      setSetup(await fetchGithubSetupStatus(fetchOpts()));
    } catch {
      setSetup(null);
    }
  }, [fetchOpts]);

  useEffect(() => {
    loadSetup();
  }, [loadSetup, github]);

  const current = stepIndex(setup);
  const grantedRepos = github?.repos?.length ? github.repos : [];
  const installUrl = setup?.install_url || github?.install_url || "";
  const repoCount = github?.repos.length ?? setup?.repos_count ?? 0;
  const ready = current === 3 && !!setup?.webhook_configured;

  async function handleRegister() {
    setRegistering(true);
    try {
      const data = await startGithubRegister(fetchOpts());
      window.open(data.register_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      onError(String(e));
    } finally {
      setRegistering(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const r = await fetch(`${API_URL}/integrations/github/refresh-repos`, {
        method: "POST",
        ...fetchOpts(),
      });
      if (r.ok) {
        await onReload();
        await loadSetup();
      } else {
        onError(await r.text());
      }
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <Card title="GitHub setup" accent={settingsColors.github} wide>
      <nav className="settings-wizard-steps" aria-label="GitHub setup progress">
        {STEPS.map((step, i) => {
          // Steps before the current one are done; the final "Ready" step also
          // shows done once the integration is actually ready (it is never
          // "before current", so it would otherwise never get a check).
          const done = i < current || (i === current && ready);
          const active = i === current && !ready;
          return (
            <div
              key={step.id}
              className={`settings-wizard-step${done ? " is-done" : ""}${active ? " is-active" : ""}`}
            >
              <span className="settings-wizard-step-num">{done ? "✓" : i + 1}</span>
              <span className="settings-wizard-step-label">{step.label}</span>
            </div>
          );
        })}
      </nav>

      <div className="settings-wizard-panel">
        {current === 0 && (
          <>
            <p className="settings-wizard-lead">
              Create an Orqis GitHub App on this server. Credentials are saved under{" "}
              <code>secrets/</code> and loaded without a restart.
            </p>
            {setup?.registration_allowed ? (
              <div className="settings-wizard-actions">
                <button
                  type="button"
                  className="settings-btn settings-btn-github"
                  disabled={registering}
                  onClick={handleRegister}
                >
                  {registering ? "Opening GitHub…" : "Register GitHub App"}
                </button>
                <button
                  type="button"
                  className="settings-link-btn"
                  onClick={() => loadSetup().then(onReload)}
                >
                  I completed registration — refresh
                </button>
              </div>
            ) : setup?.app_configured ? (
              <Hint>GitHub App credentials detected — continue to installation.</Hint>
            ) : (
              <Hint tone="warn">
                App registration unavailable in hosted mode. Set <code>GITHUB_APP_*</code> env vars
                manually or enable dev mode for self-hosted registration.
              </Hint>
            )}
          </>
        )}

        {current === 1 && setup?.app_configured && (
          <>
            <p className="settings-wizard-lead">
              Install the app on the repositories Orqis should monitor and open fix PRs against.
            </p>
            <Row label="App" value={setup.app_slug ?? "configured"} tone={settingsColors.green} />
            {installUrl ? (
              <a href={installUrl} className="settings-btn settings-btn-github">
                Install GitHub App on your repos
              </a>
            ) : (
              <Hint tone="warn">Install URL unavailable — refresh after registration completes.</Hint>
            )}
          </>
        )}

        {current === 2 && setup?.connected && (
          <>
            {!setup.webhook_configured && (
              <>
                <Hint tone="warn">
                  Webhook secret not set. PR merge events may rely on polling until configured.
                </Hint>
                <Row label="Webhook URL" value={setup.webhook_url} mono />
                <Hint>
                  For local dev run <code>python scripts/tunnel_webhook.py</code>, set{" "}
                  <code>ORQIS_PUBLIC_URL</code> to the tunnel URL, then re-register the app.
                </Hint>
              </>
            )}
            {repoCount === 0 && (
              <>
                <Hint tone="warn">No repositories granted yet. Install the app and select repos.</Hint>
                {installUrl && (
                  <a href={installUrl} className="settings-btn settings-btn-github">
                    Grant repository access
                  </a>
                )}
              </>
            )}
            {setup.webhook_configured && repoCount > 0 && (
              <Hint>Almost there — refresh repos if you just updated installation access.</Hint>
            )}
          </>
        )}

        {setup?.connected && (
          <div className="settings-wizard-connected">
            <Row
              label="Status"
              value={`Connected · ${repoCount} repo${repoCount === 1 ? "" : "s"}`}
              tone={settingsColors.green}
            />
            {github?.account_login && <Row label="Account" value={github.account_login} />}
            <button
              type="button"
              className="settings-btn settings-btn-ghost"
              disabled={refreshing}
              onClick={handleRefresh}
            >
              {refreshing ? "Refreshing…" : "Refresh repos"}
            </button>
          </div>
        )}

        {ready && (
          <p className="settings-wizard-ready">
            GitHub integration ready — configure repo routing below.
          </p>
        )}
      </div>

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
  );
}
