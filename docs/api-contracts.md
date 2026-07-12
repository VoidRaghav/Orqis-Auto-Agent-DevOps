# Orqis API contracts

Stable shapes for parallel frontend/backend work. Additive changes only during upgrade waves.

## Incident

- `GET /incidents` — list, workspace-scoped when multi-tenant
- `GET /incidents/{id}` — full incident including `status`, `diff`, `validation_errors`, `pr_url`, `cost_recovered_usd`
- Status flow: `detected` → `located` → `patched` | `low_confidence` → `approved` | `pr_open` → `resolved`

## Settings

- `GET /settings` / `PUT /settings` — `WorkspaceSettings`:
  - `default_repo`, `default_branch`, `source_repo_map`, `repos`
  - `hot_reload_webhook_url`, `auto_merge_enabled`, `pr_low_confidence`

## GitHub

- `GET /integrations/github/connect` — `GithubConnectInfo`: `configured`, `connected`, `install_url`, `repos`, `account_login`
- `POST /integrations/github/refresh-repos` — *(planned Wave 1 Track 3)*

## Workspace (multi-tenant)

- `GET /workspace/members`, `POST/DELETE /workspace/invites`
- `GET/POST /workspace/api-keys`
- `GET /workspace/audit?limit=30`

## WebSocket events

- `incident.updated`, `incident.pr_opened`, `settings.updated`

## Planned (Wave 1 UX)

- `GET /workspace/sources` — recent log sources for autocomplete
- `GET /incidents/stats` — `{ total_cost_recovered_usd, count_by_status }`
