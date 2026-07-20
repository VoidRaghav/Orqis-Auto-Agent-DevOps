import { API_URL, MULTI_TENANT } from "./env";
import type {
  GithubConnectInfo,
  GithubSetupStatus,
  IdeSetupInfo,
  WorkspaceAuditEntry,
  WorkspaceSettings,
} from "./types";

export function apiFetchOpts(adminToken = ""): RequestInit {
  return {
    credentials: MULTI_TENANT ? "include" : "same-origin",
    headers: {
      ...(adminToken ? { "X-Orqis-Admin-Token": adminToken } : {}),
    },
  };
}

export function apiJsonOpts(adminToken = "", method = "GET"): RequestInit {
  return {
    method,
    ...apiFetchOpts(adminToken),
    headers: {
      "Content-Type": "application/json",
      ...(adminToken ? { "X-Orqis-Admin-Token": adminToken } : {}),
    },
  };
}

export async function fetchGithubConnect(adminToken = ""): Promise<GithubConnectInfo> {
  const r = await fetch(`${API_URL}/integrations/github/connect`, apiFetchOpts(adminToken));
  return r.json();
}

export async function fetchGithubSetupStatus(opts: RequestInit = {}): Promise<GithubSetupStatus> {
  const r = await fetch(`${API_URL}/integrations/github/setup-status`, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startGithubRegister(opts: RequestInit = {}): Promise<{ register_url: string }> {
  const r = await fetch(`${API_URL}/integrations/github/register/start`, {
    method: "POST",
    ...opts,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type GithubVerifySetup = {
  ok: boolean;
  checks: {
    app_configured: boolean;
    installation_connected: boolean;
    webhook_configured: boolean;
    repos_granted: boolean;
    repo_accessible: boolean;
  };
  probe_repo: string | null;
  repos_count: number;
};

export async function verifyGithubSetup(opts: RequestInit = {}): Promise<GithubVerifySetup> {
  const r = await fetch(`${API_URL}/integrations/github/verify-setup`, {
    method: "POST",
    ...opts,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchSettings(adminToken = ""): Promise<WorkspaceSettings> {
  const r = await fetch(`${API_URL}/settings`, apiFetchOpts(adminToken));
  return r.json();
}

export async function fetchIdeSetup(): Promise<IdeSetupInfo> {
  const r = await fetch(`${API_URL}/integrations/ide-setup`);
  return r.json();
}

export async function saveSettings(
  body: Record<string, unknown>,
  adminToken = "",
): Promise<Response> {
  return fetch(`${API_URL}/settings`, {
    method: "PUT",
    ...apiJsonOpts(adminToken, "PUT"),
    body: JSON.stringify(body),
  });
}

export type ApiKeySummary = { id: string; prefix: string; label: string };
export type MemberSummary = { github_id: number; login: string; role: string };
export type InviteSummary = { token: string; created_at: string; url?: string };

export async function fetchApiKeys(adminToken = ""): Promise<ApiKeySummary[]> {
  const r = await fetch(`${API_URL}/workspace/api-keys`, apiFetchOpts(adminToken));
  return r.ok ? r.json() : [];
}

export async function fetchAuditLog(adminToken = ""): Promise<WorkspaceAuditEntry[]> {
  const r = await fetch(`${API_URL}/workspace/audit?limit=30`, apiFetchOpts(adminToken));
  return r.ok ? r.json() : [];
}

export async function fetchMembers(adminToken = ""): Promise<MemberSummary[]> {
  const r = await fetch(`${API_URL}/workspace/members`, apiFetchOpts(adminToken));
  return r.ok ? r.json() : [];
}

export async function fetchInvites(adminToken = ""): Promise<InviteSummary[]> {
  const r = await fetch(`${API_URL}/workspace/invites`, apiFetchOpts(adminToken));
  return r.ok ? r.json() : [];
}

export async function fetchWorkspaceSources(adminToken = ""): Promise<string[]> {
  const r = await fetch(`${API_URL}/workspace/sources`, apiFetchOpts(adminToken));
  if (!r.ok) return [];
  const data = await r.json();
  return data.sources ?? [];
}

export function rowsToMap(rows: { source: string; repo: string }[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { source, repo } of rows) {
    const s = source.trim();
    if (s && repo) out[s] = repo;
  }
  return out;
}
