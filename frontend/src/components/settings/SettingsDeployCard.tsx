import type { WorkspaceSettings } from "@/lib/types";
import { Card, Field, settingsColors } from "./SettingsUi";

type Props = {
  settings: WorkspaceSettings;
  onSettingsChange: (s: WorkspaceSettings) => void;
};

export default function SettingsDeployCard({ settings, onSettingsChange }: Props) {
  return (
    <Card title="Deploy" accent={settingsColors.amber}>
      <Field label="Hot-reload URL">
        <input
          value={settings.hot_reload_webhook_url}
          onChange={(e) => onSettingsChange({ ...settings, hot_reload_webhook_url: e.target.value })}
          className="settings-input"
          placeholder="https://app.example.com/orqis/reload"
        />
      </Field>
      <Field label="Default branch">
        <input
          value={settings.default_branch}
          onChange={(e) => onSettingsChange({ ...settings, default_branch: e.target.value })}
          className="settings-input settings-input-sm"
        />
      </Field>
    </Card>
  );
}
