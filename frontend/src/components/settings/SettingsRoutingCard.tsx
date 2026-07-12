import type { WorkspaceSettings } from "@/lib/types";
import { Card, Field, Hint, RepoSelect, settingsColors } from "./SettingsUi";

type Props = {
  settings: WorkspaceSettings;
  grantedRepos: string[];
  githubConnected: boolean;
  mapRows: { source: string; repo: string }[];
  recentSources: string[];
  onSettingsChange: (s: WorkspaceSettings) => void;
  onMapRowsChange: (rows: { source: string; repo: string }[]) => void;
};

export default function SettingsRoutingCard({
  settings,
  grantedRepos,
  githubConnected,
  mapRows,
  recentSources,
  onSettingsChange,
  onMapRowsChange,
}: Props) {
  return (
    <Card title="Repositories" accent={settingsColors.github} wide>
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
              onChange={(repo) => onSettingsChange({ ...settings, default_repo: repo })}
            />
          </Field>

          <div className="settings-divider" />

          <Field label="Source → repo (optional)">
            {mapRows.length === 0 && <span className="settings-muted">Uses default for all sources.</span>}
            {mapRows.map((row, i) => (
              <div key={i} className="settings-map-row">
                <input
                  value={row.source}
                  list="orqis-source-list"
                  onChange={(e) => {
                    const next = [...mapRows];
                    next[i] = { ...next[i], source: e.target.value };
                    onMapRowsChange(next);
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
                    onMapRowsChange(next);
                  }}
                />
                <button
                  type="button"
                  onClick={() => onMapRowsChange(mapRows.filter((_, n) => n !== i))}
                  className="settings-icon-btn"
                  aria-label="Remove"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => onMapRowsChange([...mapRows, { source: "", repo: "" }])}
              className="settings-link-btn"
            >
              + Add mapping
            </button>
            {recentSources.length > 0 && (
              <datalist id="orqis-source-list">
                {recentSources.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            )}
          </Field>
        </>
      )}
    </Card>
  );
}
