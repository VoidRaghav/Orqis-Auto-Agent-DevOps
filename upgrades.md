# Orqis — Future Upgrades

Prioritized backlog. **Shipped items struck through.**

## 1. GitHub integration (close the loop)
- ~~**Installation repo refresh**~~ — `POST /integrations/github/refresh-repos` + Settings button
- ~~**Per-repo default branch**~~ — `repo_default_branches` populated on refresh; `resolve_base_branch()`
- ~~**Public webhook delivery (partial)**~~ — `scripts/tunnel_webhook.py` + `docs/local-dev.md`
- **Smoother App onboarding** — in-product wizard still partial; `GET /integrations/github/setup-status` added; manifest script idempotent

## 2. RCA / fix quality
- ~~**Stronger patch model (partial)**~~ — LLM readiness check on startup via `interpreter.check_readiness()`
- ~~**Broaden deterministic remediation (partial)**~~ — `for` loops guarded alongside `while`
- ~~**Patch staleness handling**~~ — `PATCH_STALE` + dashboard retry UX
- **Multi-file fixes** — `diff_split.py` helper added; full multi-commit PR path still TODO

## 3. Testing & CI
- ~~**Automated test suite (partial)**~~ — unit tests in `tests/unit/` (path_mapper, diff_engine, remediation, validator, sanitize, secret_scan)
- ~~**CI pipeline**~~ — `.github/workflows/ci.yml` + `make ci`

## 4. Security & multi-tenancy
- ~~**Real auth**~~ — shipped (OAuth, sessions, invites)
- ~~**Per-workspace isolation**~~ — shipped
- ~~**Secret scanning on diffs**~~ — `scan_for_secrets()` blocks PR open

## 5. UX / dashboard
- ~~**Source autocomplete**~~ — `GET /workspace/sources` + datalist in Settings routing
- ~~**Incident detail timeline**~~ — `IncidentTimeline` component
- ~~**Cost analytics**~~ — RECOVERED KPI + `GET /incidents/stats`
- ~~**Notifications**~~ — webhook + Slack settings + dispatcher

## 6. Ingestion & detection
- ~~**More log sources (partial)**~~ — `/ingest/datadog`, `/ingest/cloudwatch`, `/ingest/otel`
- ~~**Smarter anomaly detection (partial)**~~ — adaptive per-source threshold
- ~~**Dedup tuning**~~ — structural fingerprint (type + frame + message)

## 7. IDE integration depth
- ~~**Push notifications to IDEs (partial)**~~ — MCP `watch_incidents` tool
- ~~**Apply-from-IDE round trip (partial)**~~ — `open_pr` / `approve` return status + pr_url

## 8. Deployment & ops
- ~~**One-command deploy**~~ — `docker-compose.yml` + `make up`
- ~~**Health/observability**~~ — `GET /health/ready` with Redis + LLM + GitHub checks

---

## Remaining (post-wave)

| Item | Notes |
|------|-------|
| Full onboarding wizard | Settings step UI for app credentials → install → webhook verify |
| Multi-file PR commits | Wire `diff_split` into `open_fix_pr` for 2+ files |
| WS Redis pub/sub | Multi-replica dashboard |
| Workspace switcher | Users in multiple workspaces |
| Full in-product GitHub App creation | Beyond idempotent manifest script |
