import { API_URL } from "@/lib/env";
import type { InviteSummary, MemberSummary } from "@/lib/api";
import { Card, Hint, settingsColors } from "./SettingsUi";

type Props = {
  members: MemberSummary[];
  pendingInvites: InviteSummary[];
  inviteUrl: string | null;
  fetchOpts: () => RequestInit;
  onInviteCreated: (url: string) => void;
  onReload: () => Promise<void>;
  onError: (msg: string) => void;
};

export default function SettingsTeamCard({
  members,
  pendingInvites,
  inviteUrl,
  fetchOpts,
  onInviteCreated,
  onReload,
  onError,
}: Props) {
  return (
    <Card title="Team" accent={settingsColors.blue}>
      <Hint>Invite teammates — they sign in with GitHub to join this workspace.</Hint>
      <ul className="settings-ide-list">
        {members.map((m) => (
          <li key={m.github_id}>
            <span>
              {m.login} <span className="settings-muted">({m.role})</span>
            </span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="settings-btn settings-btn-ghost"
        onClick={async () => {
          const r = await fetch(`${API_URL}/workspace/invites`, {
            method: "POST",
            ...fetchOpts(),
          });
          if (r.ok) {
            const data = await r.json();
            onInviteCreated(data.url);
            await onReload();
          } else {
            onError(await r.text());
          }
        }}
      >
        Create invite link
      </button>
      {inviteUrl && (
        <div className="settings-banner settings-banner-ok" style={{ wordBreak: "break-all" }}>
          Share once: <code>{inviteUrl}</code>
        </div>
      )}
      {pendingInvites.length > 0 && (
        <ul className="settings-ide-list">
          {pendingInvites.map((inv) => (
            <li key={inv.token}>
              <span className="settings-ide-path">{inv.url}</span>
              <button
                type="button"
                className="settings-link-btn"
                onClick={async () => {
                  await fetch(`${API_URL}/workspace/invites/${inv.token}`, {
                    method: "DELETE",
                    ...fetchOpts(),
                  });
                  await onReload();
                }}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
