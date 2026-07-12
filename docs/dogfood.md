# Orqis dogfood testing

Dogfood testing validates Orqis end-to-end against a **separate user project** (the buggy `orqis-test-agent` repo) while the harness lives in this repo. Two tiers:

| Tier | Test file | What it proves | Requires |
|------|-----------|----------------|----------|
| **A** | `tests/test_pipeline_runaway.py` | Backend pipeline: traces → incident → patch → HTTP approve → behavioral fix | Redis, backend, admin token |
| **B** | `tests/test_agent_ide_flow.py` | Cursor SDK agent uses Orqis MCP (`list_incidents` / `get_incident` before `approve_incident`) | Tier A green + `CURSOR_API_KEY` |

Tier A is an **integration test**, not proof that an LLM agent reasons correctly. Tier B covers the agent/MCP path.

---

## Security (read first)

**R4 — never dogfood on a host that also holds production GitHub App credentials.**

If `GITHUB_APP_PRIVATE_KEY` or `GITHUB_APP_PRIVATE_KEY_PATH` points at your real production PEM on the same machine where you run the harness, a misconfigured approve/open-pr path could touch live repos. For dogfood:

- Use a **throwaway GitHub App** install on a test org/repo, **or**
- Leave GitHub App env vars **unset** during harness runs (local approve only, no PR automation), **or**
- Run dogfood in an isolated VM/container without production secrets.

`ORQIS_ADMIN_TOKEN` is **required** for all dogfood runs. Write endpoints (`approve`, `dismiss`, `open-pr`, `resolve`, `PUT /settings`) return **401** when it is unset.

Generate a token:

```bash
openssl rand -hex 32
```

---

## Prerequisites

- Python 3.9+ (3.10+ for Tier B / `cursor-sdk`)
- Redis running locally (`redis://localhost:6379` or set `REDIS_URL`)
- Orqis installed editable with dev deps: `pip install -e ".[dev]"`
- A checkout of the test user project (see below)

---

## 1. Test user project (`orqis-test-agent`)

The harness patches files under `ORQIS_PROJECT_ROOT`. That directory must look like a real customer repo: `src/`, `fixtures/`, `.mcp.json` — **no harness code**.

**Option A — bundled copy (quick local dev):**

```bash
export ORQIS_PROJECT_ROOT=/path/to/Orqis-Auto-Agent-DevOps/test-agent
```

**Option B — separate clone (matches production layout):**

```bash
git clone https://github.com/Siddarthb07/orqis-test-agent.git /path/to/orqis-test-agent
export ORQIS_PROJECT_ROOT=/path/to/orqis-test-agent
```

Windows PowerShell:

```powershell
$env:ORQIS_PROJECT_ROOT = "C:\path\to\orqis-test-agent"
```

`preflight.py` aborts if `$ORQIS_PROJECT_ROOT/src/refund_agent.py` is missing.

---

## 2. Orqis environment

Copy and edit `.env` from `.env.example`:

```bash
cp .env.example .env
```

Minimum for dogfood:

| Variable | Required | Notes |
|----------|----------|-------|
| `ORQIS_ADMIN_TOKEN` | **Yes** | Same value in MCP `env` if using Cursor |
| `ORQIS_PROJECT_ROOT` | **Yes** | Path to test-agent checkout |
| `REDIS_URL` | Yes (default ok) | `redis://localhost:6379` |
| `ORQIS_BACKEND_URL` | No | Default `http://localhost:8000` |
| `CURSOR_API_KEY` | Tier B only | Cursor API key for SDK agent tests |
| `GITHUB_APP_*` | **No for harness** | See R4 above |

Example:

```bash
export ORQIS_ADMIN_TOKEN="<your-token>"
export ORQIS_PROJECT_ROOT=/path/to/orqis-test-agent
# Tier B only:
export CURSOR_API_KEY="<cursor-api-key>"
```

---

## 3. Start services

**Terminal 1 — Redis** (if not already running):

```bash
# Docker example
docker run -d --name orqis-redis -p 6379:6379 redis:7-alpine

# or use an existing local Redis
redis-cli ping   # expect PONG
```

**Terminal 2 — Orqis backend:**

```bash
pip install -e ".[dev]"
orqis start
```

Verify:

```bash
curl -s http://localhost:8000/health
# {"status":"ok", ...}
```

---

## 4. Preflight

Hard-abort checks before any harness test (R5):

```bash
python scripts/preflight.py
```

Validates: `ORQIS_ADMIN_TOKEN` set, Redis reachable, backend healthy, `orqis` CLI on `PATH`, `ORQIS_PROJECT_ROOT` points at a tree with `src/refund_agent.py`.

---

## 5. Run tests

### One-shot runners

**Linux / macOS / Git Bash:**

```bash
bash scripts/run_dogfood.sh
```

**Windows PowerShell:**

```powershell
.\scripts\run_dogfood.ps1
```

**Make:**

```bash
make test-agent
```

All three: preflight → Tier A → Tier B (Tier B skipped with a message if `CURSOR_API_KEY` is unset).

### Manual pytest

**Tier A** (pipeline, no LLM):

```bash
pytest tests/test_pipeline_runaway.py -v
```

**Tier B** (Cursor SDK + MCP ordering) — only after **5 consecutive Tier A greens**:

```bash
pytest tests/test_agent_ide_flow.py -v
```

Pytest markers: `tier_a`, `tier_b` (see `pyproject.toml`).

### What Tier A does

1. `POST /demo/reset?clear=true` — zero open incidents
2. Copy `fixtures/` → `ORQIS_PROJECT_ROOT/src/`
3. POST repeated `tool.start` traces (runaway loop detector)
4. Poll until incident `status=patched` with a diff
5. `POST /incidents/{id}/approve` via HTTP (no agent)
6. Assert `ast.parse` on patched file + `resolve_refund("1042")` returns within 2s

### What Tier B does

Same reset/trigger, then spawns a local Cursor SDK agent with Orqis MCP stdio. Fails if `approve_incident` runs before both `list_incidents` and `get_incident`. Logs `X-Orqis-Trace-Id` per harness request for correlation.

---

## 6. Observability

Harness tests send `X-Orqis-Trace-Id: <uuid>` on reset, trace ingest, and approve calls. Grep test output or backend logs for the trace id when debugging a failed run.

Tier B also records MCP tool calls (`tests/mcp_call_log.py` proxy) for ordering assertions.

---

## 7. Troubleshooting

| Symptom | Check |
|---------|-------|
| `preflight FAIL: ORQIS_ADMIN_TOKEN` | Export token; restart shell |
| `preflight FAIL: Redis unreachable` | Start Redis; verify `REDIS_URL` |
| `preflight FAIL: backend unreachable` | Run `orqis start` in another terminal |
| `preflight FAIL: missing .../src/refund_agent.py` | Fix `ORQIS_PROJECT_ROOT` |
| Tier A timeout on `patched` | Backend logs; ensure traces hit `/trace` |
| Tier B skipped | Set `CURSOR_API_KEY`; `pip install -e ".[dev]"` on Python 3.10+ |
| Approve returns 401 | Token mismatch between env and request header |

---

## 8. CI / stability gates

- **Enable Tier B in CI** only after 5 consecutive Tier A passes locally.
- **9/10 sign-off** (per council plan): R1–R15 complete, full preflight→A→B green, 2 weeks Tier B stability.
- Pin the test-agent git ref in `tests/conftest.py` when using an external clone (`ORQIS_TEST_AGENT_REF`).

---

## Quick reference

```bash
export ORQIS_PROJECT_ROOT=/path/to/orqis-test-agent
export ORQIS_ADMIN_TOKEN=$(openssl rand -hex 32)   # or use existing
pip install -e ".[dev]"
orqis start                                          # separate terminal
python scripts/preflight.py
pytest tests/test_pipeline_runaway.py -v             # Tier A
pytest tests/test_agent_ide_flow.py -v               # Tier B (needs CURSOR_API_KEY)
```

See also: [`test-agent/README.md`](../test-agent/README.md) for the user-project layout.
