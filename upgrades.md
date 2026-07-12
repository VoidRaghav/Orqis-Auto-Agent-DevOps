# Orqis — Future Upgrades

A prioritized list of upgrades, grounded in the current state of the codebase.

## 1. GitHub integration (close the loop)
- **Public webhook delivery** — today PR-merge detection falls back to `poll_open_prs()` because localhost can't receive webhooks. Add first-class tunnel support (bundled `cloudflared`/ngrok helper) or document a hosted deploy so `pull_request` merge events arrive in real time.
- **Smoother App onboarding** — the manifest flow (`scripts/create_github_app.py`) is fragile and one-shot. Make it a guided in-product setup with retry/resume, and detect/repair an orphaned app instead of creating duplicates.
- **Installation repo refresh** — re-sync `settings.repos` on a timer and on a "Refresh repos" button, so newly granted repos appear without reconnecting.
- **Per-repo default branch** — `default_branch` is global; resolve it per repo from the GitHub API (`get_default_branch`) and cache it.

## 2. RCA / fix quality
- **Stronger patch model** — the LLM path needs a real model (Ollama 3b is weak and wasn't even pulled). Add provider auto-detection, a model-readiness check on startup, and a quality gate before opening a PR.
- **Broaden deterministic remediation** — `guard_runaway_loop` only handles a `while` loop directly inside the failing function. Extend to `for` loops, nested/recursive loops, and other templated classes (retry-without-backoff, unbounded pagination).
- **Multi-file fixes** — current pipeline assumes a single file/location. Support patches spanning multiple files.
- **Patch staleness handling** — surface and auto-rebase `patch_stale` incidents when the base branch moves.

## 3. Testing & CI
- **Automated test suite** — there are no committed tests. Add unit tests for `source_resolver`, `path_mapper`, `diff_engine`, `remediation`, and `validator`, plus an E2E test that replaces the manual `scripts/drive_runaway_loop.py`.
- **CI pipeline** — GitHub Actions running `py_compile`/pytest + `tsc`/`next build` on PRs to this repo.

## 4. Security & multi-tenancy
- **Real auth** — replace the single `ORQIS_ADMIN_TOKEN` with user sessions/RBAC so teams can share an instance.
- **Per-workspace isolation** — settings/incidents are currently a single global workspace in Redis; key them per installation/org for multi-tenant use.
- **Secret scanning on diffs** — extend `pr_service.sanitize` with a proper secret-detection pass before any diff is posted.

## 5. UX / dashboard
- **Source autocomplete** — populate the per-source routing inputs with recently-seen log sources (from `/incidents`/`/events`) so users pick instead of recall.
- **Incident detail view** — richer timeline (detected → located → patched → PR → merged) with diffs and validation results inline.
- **Cost analytics** — aggregate `cost_recovered_usd` across incidents into a "money saved" dashboard.
- **Notifications** — Slack/email/webhook when an incident opens a PR or needs review.

## 6. Ingestion & detection
- **More log sources** — first-class Datadog, CloudWatch, GCP, and OpenTelemetry ingestion alongside the current drain/Sentry paths.
- **Smarter anomaly detection** — the runaway-loop detector is a fixed threshold/window; add adaptive thresholds and more behavioral patterns (cost spikes, error-rate regressions).
- **Dedup tuning** — fingerprinting is first-200-chars; add structural fingerprints to better collapse related errors.

## 7. IDE integration depth
- **Push notifications to IDEs** — beyond MCP pull tools, proactively surface new incidents in-editor.
- **Apply-from-IDE round trip** — let the MCP `approve`/`open_pr` flow report status back into the editor.

## 8. Deployment & ops
- **One-command deploy** — polished Railway/Docker Compose with Redis, backend, and frontend wired together.
- **Health/observability** — structured logging, metrics endpoint, and a readiness check that verifies Redis, LLM provider, and GitHub auth.
