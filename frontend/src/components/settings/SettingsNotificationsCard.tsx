import { API_URL } from "@/lib/env";
import type { WorkspaceSettings } from "@/lib/types";
import { Card, Field, Hint, settingsColors } from "./SettingsUi";

type Props = {
  settings: WorkspaceSettings;
  onSettingsChange: (s: WorkspaceSettings) => void;
  fetchOpts: () => RequestInit;
  onTestResult: (ok: boolean, msg: string) => void;
};

export default function SettingsNotificationsCard({
  settings,
  onSettingsChange,
  fetchOpts,
  onTestResult,
}: Props) {
  return (
    <Card title="Notifications" accent={settingsColors.blue}>
      <Hint>Webhook or Slack incoming webhook when incidents are patched or PRs open.</Hint>
      <Field label="Generic webhook URL">
        <input
          value={settings.notification_webhook_url ?? ""}
          onChange={(e) =>
            onSettingsChange({ ...settings, notification_webhook_url: e.target.value })
          }
          className="settings-input"
          placeholder="https://hooks.example.com/orqis"
        />
      </Field>
      <Field label="Slack webhook URL">
        <input
          value={settings.notification_slack_url ?? ""}
          onChange={(e) =>
            onSettingsChange({ ...settings, notification_slack_url: e.target.value })
          }
          className="settings-input"
          placeholder="https://hooks.slack.com/services/..."
        />
      </Field>
      <button
        type="button"
        className="settings-btn settings-btn-ghost"
        onClick={async () => {
          const r = await fetch(`${API_URL}/workspace/notifications/test`, {
            method: "POST",
            ...fetchOpts(),
          });
          if (r.ok) {
            onTestResult(true, "Test notification sent.");
          } else {
            onTestResult(false, await r.text());
          }
        }}
      >
        Send test
      </button>
    </Card>
  );
}
