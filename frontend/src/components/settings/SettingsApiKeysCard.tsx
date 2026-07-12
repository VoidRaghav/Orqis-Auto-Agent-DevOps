import { API_URL } from "@/lib/env";
import type { ApiKeySummary } from "@/lib/api";
import { Card, Hint, settingsColors } from "./SettingsUi";

type Props = {
  apiKeys: ApiKeySummary[];
  newKey: string | null;
  fetchOpts: () => RequestInit;
  onNewKey: (key: string) => void;
  onReload: () => Promise<void>;
};

export default function SettingsApiKeysCard({ apiKeys, newKey, fetchOpts, onNewKey, onReload }: Props) {
  return (
    <Card title="Ingest API keys" accent={settingsColors.amber}>
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
            onNewKey(data.key);
            await onReload();
          }
        }}
      >
        Generate key
      </button>
    </Card>
  );
}
