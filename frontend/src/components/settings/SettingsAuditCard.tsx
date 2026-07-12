import type { WorkspaceAuditEntry } from "@/lib/types";
import { mono } from "@/lib/tokens";
import { Card, Hint, settingsColors } from "./SettingsUi";

type Props = {
  auditLog: WorkspaceAuditEntry[];
};

export default function SettingsAuditCard({ auditLog }: Props) {
  return (
    <Card title="Audit log" accent={settingsColors.dim} wide>
      <Hint>Recent workspace write actions (30 days retention)</Hint>
      {auditLog.length === 0 ? (
        <span className="settings-muted">No audit entries yet.</span>
      ) : (
        <ul className="settings-audit-list">
          {auditLog.map((entry) => (
            <li key={entry.id} className="settings-audit-row">
              <span className="settings-audit-time">{new Date(entry.timestamp).toLocaleString()}</span>
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
  );
}
