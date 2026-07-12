import type { WorkspaceSettings } from "@/lib/types";
import { Card, Toggle, settingsColors } from "./SettingsUi";

type Props = {
  settings: WorkspaceSettings;
  onSettingsChange: (s: WorkspaceSettings) => void;
};

export default function SettingsAutomationCard({ settings, onSettingsChange }: Props) {
  return (
    <Card title="Automation" accent={settingsColors.amber}>
      <Toggle
        label="Low-confidence PRs"
        checked={settings.pr_low_confidence}
        onChange={(v) => onSettingsChange({ ...settings, pr_low_confidence: v })}
      />
      <Toggle
        label="Auto-merge (config only)"
        checked={settings.auto_merge_enabled}
        onChange={(v) => onSettingsChange({ ...settings, auto_merge_enabled: v })}
        danger
      />
    </Card>
  );
}
