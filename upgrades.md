# Orqis — Future Upgrades

Prioritized backlog. **Shipped items struck through.**
Aligned with council verdict 2026-07-16 (`VIABLE_WITH_CHANGES`).

## 1. GitHub integration (close the loop)
- ~~**Installation repo refresh**~~ — `POST /integrations/github/refresh-repos` + Settings button
- ~~**Per-repo default branch**~~ — `repo_default_branches` populated on refresh; `resolve_base_branch()`
- ~~**Public webhook delivery (partial)**~~ — `scripts/tunnel_webhook.py` + `docs/local-dev.md`
- ~~**Multi-file fix PRs**~~ — `diff_split.split_by_file` + `client.commit_files` wired in `open_fix_pr`
- **Smoother App onboarding (MVP next)** — finish wizard: credentials → install → webhook verify → ready (no full in-product App creation)

## 2. RCA / fix quality
- ~~**Stronger patch model (partial)**~~ — LLM readiness check on startup via `interpreter.check_readiness()`
- ~~**Broaden deterministic remediation (partial)**~~ — `for` loops guarded alongside `while`
- ~~**Patch staleness handling**~~ — `PATCH_STALE` + dashboard retry UX
- ~~**Write-path path safety**~~ — `orqis/rca/safe_path.py`: reject traversal/absolute/`.git`/`.github`; auto-merge denylist for CI configs
- ~~**Detector Tier-A fixtures (capped)**~~ — top 5 detectors + `make detectors` / CI gate (`tests/unit/test_detectors_top5.py`)
- **Patch quality gate** — reject weak/noisy patches before PR
- **Auto-rebase stale PRs** — surface + rebase on base-branch move

## 3. Testing & CI
- ~~**Automated test suite (partial)**~~ — unit tests in `tests/unit/`
- ~~**CI pipeline**~~ — `.github/workflows/ci.yml` + `make ci`
- **CI dogfood gate** — Tier A in Actions after local 5-green rule

## 4. Security & multi-tenancy
- ~~**Real auth**~~ — shipped (OAuth, sessions, invites)
- ~~**Per-workspace isolation**~~ — shipped
- ~~**Secret scanning on diffs**~~ — `scan_for_secrets()` blocks PR open
- ~~**MULTI_TENANT single source of truth**~~ — only `ORQIS_MULTI_TENANT` (not inferred from `DATABASE_URL`)
- **Workspace switcher** — deferred until real multi-workspace demand; must re-derive membership server-side (no raw client workspace header trust)

## 5. UX / dashboard
- ~~**Source autocomplete**~~ — `GET /workspace/sources` + datalist in Settings routing
- ~~**Incident detail timeline**~~ — `IncidentTimeline` component
- ~~**Cost analytics**~~ — RECOVERED KPI + `GET /incidents/stats`
- ~~**Notifications**~~ — webhook + Slack settings + dispatcher
- **Email notifications** — alert on PR open / needs review

## 6. Ingestion & detection
- ~~**More log sources (partial)**~~ — `/ingest/datadog`, `/ingest/cloudwatch`, `/ingest/otel`
- ~~**Smarter anomaly detection (partial)**~~ — adaptive per-source threshold
- ~~**Dedup tuning**~~ — structural fingerprint (type + frame + message)
- **Ingest queue metrics** — depth / shed on `/health/ready`

## 7. IDE integration depth
- ~~**Push notifications to IDEs (partial)**~~ — MCP `watch_incidents` tool
- ~~**Apply-from-IDE round trip (partial)**~~ — `open_pr` / `approve` return status + pr_url
- **Deeper IDE apply** — local apply via MCP (beyond open PR)

## 8. Deployment & ops
- ~~**One-command deploy**~~ — `docker-compose.yml` + `make up`
- ~~**Health/observability**~~ — `GET /health/ready` with Redis + LLM + GitHub checks
- **WS Redis pub/sub** — multi-replica dashboard (hard blocker before horizontal scale; not current single-replica priority)
- **Compose conflict-safe ports** — avoid clashing with host `:8000`/`:6379`

---

## Active execution order (council 2026-07-16)

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Write-path hardening + doc reconcile | **done** |
| 2 | GitHub onboarding wizard MVP (4-step + verify-setup) | **done** |
| 3 | Detector fixtures for top 5 + CI gate | **done** |

## Do not do (council)

- Workspace switcher *now* (no demand evidence; IDOR risk if naive)
- WS Redis pub/sub *now* (correct before multi-replica; not today’s blocker)
- Expanding auto-merge-eligible detectors before path allowlist was fixed
- Full in-product GitHub App creation as part of the wizard
