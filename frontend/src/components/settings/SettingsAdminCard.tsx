import { MULTI_TENANT } from "@/lib/env";
import { Card, Field, Hint, settingsColors } from "./SettingsUi";

type Props = {
  adminToken: string;
  onAdminTokenChange: (token: string) => void;
};

export default function SettingsAdminCard({ adminToken, onAdminTokenChange }: Props) {
  return (
    <Card title="Admin" accent={settingsColors.dim}>
      {MULTI_TENANT ? (
        <Hint>Hosted multi-tenant uses session + API keys. Admin token is local dev only.</Hint>
      ) : (
        <>
          <Field label="Token">
            <input
              value={adminToken}
              onChange={(e) => onAdminTokenChange(e.target.value)}
              type="password"
              className="settings-input"
              placeholder="ORQIS_ADMIN_TOKEN"
            />
          </Field>
          <Hint>Stored in browser only.</Hint>
        </>
      )}
    </Card>
  );
}
