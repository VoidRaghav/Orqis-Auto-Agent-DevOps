"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/env";
import type { GithubConnectInfo, GithubSetupStatus } from "@/lib/types";
import {
  fetchGithubSetupStatus,
  startGithubRegister,
  verifyGithubSetup,
  type GithubVerifySetup,
} from "@/lib/api";
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

const CHECK_LABELS: { key: keyof GithubVerifySetup["checks"]; label: string }[] = [
  { key: "app_configured", label: "App credentials" },
  { key: "installation_connected", label: "App installed" },
  { key: "repos_granted", label: "Repos granted" },
  { key: "webhook_configured", label: "Webhook configured" },
  { key: "repo_accessible", label: "Repo API access" },
];

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
  const [verifying, setVerifying] = useState(false);
  const [verify, setVerify] = useState<GithubVerifySetup | null>(null);

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
  const ready =
    current === 3 &&
    !!setup?.webhook_configured &&
    repoCount > 0 &&
    (verify?.ok ?? false);

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

  async function handleVerify() {
    setVerifying(true);
    try {
      const result = await verifyGithubSetup(fetchOpts());
      setVerify(result);
      await loadSetup();
      if (!result.ok) {
        onError("GitHub setup incomplete — see checklist below.");
      }
    } catch (e) {
      setVerify(null);
      onError(String(e));
    } finally {
      setVerifying(false);
    }
  }

  return (
    <Card title="GitHub setup" accent={settingsColors.github} wide>
      <nav className="settings-wizard-steps" aria-label="GitHub setup progress">
        {STEPS.map((step, i) => {
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
              <Hint>Almost there — verify setup to confirm repo API access.</Hint>
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
            <div className="settings-wizard-actions">
              <button
                type="button"
                className="settings-btn settings-btn-ghost"
                disabled={refreshing}
                onClick={handleRefresh}
              >
                {refreshing ? "Refreshing…" : "Refresh repos"}
              </button>
              <button
                type="button"
                className="settings-btn settings-btn-github"
                disabled={verifying}
                onClick={handleVerify}
              >
                {verifying ? "Verifying…" : "Verify setup"}
              </button>
            </div>
          </div>
        )}

        {verify && (
          <ul className="settings-wizard-checklist" aria-label="GitHub setup checklist">
            {CHECK_LABELS.map(({ key, label }) => {
              const ok = verify.checks[key];
              return (
                <li key={key} className={ok ? "is-ok" : "is-fail"}>
                  <span aria-hidden="true">{ok ? "✓" : "○"}</span> {label}
                  {key === "repo_accessible" && verify.probe_repo
                    ? ` (${verify.probe_repo})`
                    : ""}
                </li>
              );
            })}
          </ul>
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
