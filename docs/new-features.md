# Orqis — New Features

Living list of features shipped in the multi-tenant production push, plus what's next.

**Last updated:** 2026-07-10

---

## Shipped — Multi-tenant core (v1)

| Feature | What it does |
|---------|----------------|
| **GitHub OAuth login** | Sign in with GitHub → session cookie → workspace |
| **Per-workspace isolation** | Redis keys prefixed `orqis:t:{workspace_id}:*` |
| **Ingest API keys** | `orqs_…` keys on `/ingest`, `/trace`, `/events` |
| **Per-workspace GitHub App** | Signed install state + `install_id → workspace` index |
| **WebSocket rooms** | Dashboard WS scoped per workspace; ticket or cookie auth |
| **RCA tenant threading** | `_spawn()` preserves workspace in background PR pipeline |
| **Hosted mode** | `ORQIS_HOSTED=1` blocks disk apply + global admin token |
| **Startup validation** | Fail-fast on weak secrets / missing OAuth in production |
| **Legacy migration** | Auto-copy pre-tenant Redis keys → `default` workspace |
| **Frontend AuthGuard** | `/dashboard` + `/settings` require login when `VITE_MULTI_TENANT=1` |
| **Settings API keys UI** | Generate / list ingest keys in dashboard |

## Shipped — Security hardening (P0)

| Feature | What it does |
|---------|----------------|
| **WS ticket single-use** | Redis nonce, 60s TTL — replay blocked |
| **PR webhook fail-closed** | Unbound `installation_id` → `pending`, never unscoped |
| **Global webhook dedup** | `orqis:delivery:{guid}` before workspace bind |
| **Hosted MCP writes** | Workspace API key (`Bearer orqs_…`) for incident actions |
| **Audit log API** | `GET /workspace/audit` — append-only write trail |
| **Body size limits** | `ORQIS_MAX_INGEST_BODY_BYTES` on `/drain` |
| **Rate limiting** | Per-workspace ingest RPM (`ORQIS_INGEST_RATE_LIMIT`) |
| **16 tenancy tests** | HTTP isolation, ingest auth, WS ticket, store prefix |

## Shipped — P1 polish

| Feature | What it does |
|---------|----------------|
| **Audit log Settings UI** | Recent workspace actions in Settings (multi-tenant) |
| **Redis SCAN** | `store.scan_keys()` replaces blocking `KEYS` |
| **Config mismatch banner** | Warns when `VITE_MULTI_TENANT` ≠ backend `/health` |
| **MCP env hint** | Copy `.mcp.json` with `ORQIS_API_KEY` in hosted mode |
| **`installation_account_login`** | GitHub org/user name saved on App connect |

---

## Shipped — Team tier (v1.1)

| Feature | What it does |
|---------|----------------|
| **Workspace invites** | Owner creates link → teammate signs in with GitHub → joins workspace |
| **Workspace members** | Owner + member roles; members list in Settings |
| **Member authZ** | Session validated against membership on dashboard/write paths |
| **Invite preview page** | `/invite/:token` — public workspace name before sign-in |

---

## Planned — Scale & product (v1.2+)

| Feature | Priority | What it will do |
|---------|----------|-----------------|
| **WS Redis pub/sub** | P2 | Multi-replica safe real-time dashboard |
| **Workspace switcher** | P2 | Users in multiple workspaces pick active context |
| **MissionControl landing sync** | P3 | Landing demo reuses real dashboard components |
| **Repo refresh button** | P2 | Re-sync GitHub App repos without reconnect |
| **Per-repo default branch** | P2 | Resolve from GitHub API per repo |
| **Slack / email notifications** | P3 | Alert on PR open or incident needs review |
| **Source autocomplete** | P3 | Recent log sources in Settings routing |
| **Incident timeline view** | P3 | detect → locate → patch → PR → merged inline |
| **Secret scan on diffs** | P2 | Block API keys in PR bodies before post |

---

## Planned — RCA quality (from upgrades.md)

| Feature | What it will do |
|---------|-----------------|
| **Stronger patch model** | Provider readiness check; quality gate before PR |
| **Broader runaway remediation** | `for` loops, nested loops, retry-without-backoff |
| **Multi-file fixes** | Patches spanning more than one file |
| **Patch staleness / rebase** | Surface `patch_stale`; auto-rebase on branch move |

---

## Planned — Ingestion & ops

| Feature | What it does |
|---------|----------------|
| **Datadog / CloudWatch / OTel** | First-class log drains beyond Railway/Sentry |
| **Adaptive anomaly detection** | Beyond fixed threshold runaway detector |
| **One-command deploy** | Docker Compose / Railway with Redis + backend + frontend |
| **CI pipeline** | GitHub Actions: pytest + frontend build on PRs |
| **Webhook tunnel helper** | `cloudflared`/`ngrok` for local PR merge events |

---

## Enable hosted multi-tenant

```bash
# Backend
ORQIS_MULTI_TENANT=1
ORQIS_HOSTED=1
ORQIS_DEV_MODE=0
ORQIS_SESSION_SECRET=<random-32+-chars>
ORQIS_SESSION_SECURE=1
GITHUB_OAUTH_CLIENT_ID/SECRET

# Frontend build
VITE_MULTI_TENANT=1
```

Local dev unchanged: `ORQIS_MULTI_TENANT=0` → workspace `default`, no login.

---

## Council scores

| Milestone | Score |
|-----------|-------|
| Original plan (pre-impl) | ~2.10 / 5 |
| First implementation | 3.95 / 5 |
| Post P0 hardening | 4.52 / 5 |
| Post P1 polish (est.) | ~4.7 / 5 |
| Target with teams + WS pub/sub | ~4.8+ / 5 |
