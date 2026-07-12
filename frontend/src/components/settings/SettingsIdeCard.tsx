import type { IdeSetupInfo } from "@/lib/types";
import { MULTI_TENANT } from "@/lib/env";
import { Card, Hint, Row, settingsColors } from "./SettingsUi";

type Props = {
  ideSetup: IdeSetupInfo | null;
  adminToken: string;
  newKey: string | null;
  mcpCopied: boolean;
  onCopyMcp: () => void;
};

export default function SettingsIdeCard({ ideSetup, adminToken, newKey, mcpCopied, onCopyMcp }: Props) {
  return (
    <Card title="IDE / MCP" accent={settingsColors.green}>
      <Hint>One stdio server · all editors</Hint>
      {ideSetup && (
        <>
          <Row label="Command" value={ideSetup.mcp_command} mono />
          <button type="button" onClick={onCopyMcp} className="settings-btn settings-btn-ghost">
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
          {MULTI_TENANT && !newKey && (
            <p className="settings-hint">Generate an ingest API key to embed in MCP config.</p>
          )}
          {!MULTI_TENANT && !adminToken && (
            <p className="settings-hint">Set admin token below before copying MCP config.</p>
          )}
        </>
      )}
    </Card>
  );
}
