# Orqis

Autonomous self-healing ops for AI agents and DevOps pipelines.

**What it does:** monitors your logs in real time, classifies every error, generates plain-English explanations and unified diff patches, and surfaces incidents to your AI coding assistant via MCP (any MCP-compatible IDE) or a copy-paste prompt.

---

## Quick start (local)

**Prerequisites:** Python 3.9+, Redis running locally

```bash
# Install
pip install -e .

# Copy env
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY or leave LLM_PROVIDER=ollama for free local inference

# Terminal 1: start backend
orqis start

# Terminal 2: stream a log file
orqis monitor --file /var/log/app.log --source my-app

# Or pipe any process
my-process | orqis monitor --source worker

# Terminal 3 (optional): MCP server for VS Code, Cursor, Claude Code, Windsurf, …
orqis mcp

# Check health
orqis status
```

---

## Deploy on Railway (to receive Railway/Vercel drain logs)

Orqis needs to be publicly accessible so Railway and Vercel can POST logs to it.

### 1. Deploy Orqis on Railway

```bash
# In the Orqis directory
railway login
railway init
railway up
```

Railway will detect `railway.toml` and use the Dockerfile automatically.

**Required environment variables** (set in Railway dashboard → Variables):

| Variable | Value |
|---|---|
| `REDIS_URL` | Add the Railway Redis plugin — it sets this automatically |
| `ANTHROPIC_API_KEY` | Your Anthropic key (or leave unset to use Ollama) |
| `LLM_PROVIDER` | `anthropic` (for Railway deployment; Ollama needs local GPU) |
| `ORQIS_DRAIN_TOKEN` | Any long random string — copy it, you'll need it below |

After deploy, Railway gives you a public URL like `https://orqis-production.up.railway.app`.

### 2. Connect your app's Railway log drain

In your **app's** Railway project (not the Orqis project):

```
Settings → Log Drains → Add Drain
  Type: HTTP
  URL:  https://orqis-production.up.railway.app/drain?source=my-app&token=YOUR_DRAIN_TOKEN
```

That's it. Every log line your app writes is now sent to Orqis.

### 3. Connect Vercel log drain

In your Vercel project:

```
Settings → Log Drains → Add Drain
  Source: All (or pick Build / Runtime)
  Delivery format: NDJSON
  Endpoint URL: https://orqis-production.up.railway.app/drain?source=my-vercel-app&token=YOUR_DRAIN_TOKEN
```

Vercel also sends an `x-vercel-signature` header. Orqis accepts the logs regardless — signature verification is optional for now.

---

## SDK instrumentation (for LLM cost + error tracking)

Add to your Python app's entry point:

```python
import orqis
orqis.init(
    backend_url="https://orqis-production.up.railway.app",
    source="my-app",
)
```

This silently patches OpenAI, Anthropic, and LangChain clients if they are installed. No other code changes needed.

---

## IDE integration (MCP + copy-paste)

Orqis works with **any** editor or AI assistant — not just one vendor.

### Option A — MCP (recommended)

Add the Orqis MCP server to your IDE. Every MCP client spawns the same stdio process:

```bash
orqis mcp --backend-url http://localhost:8000
```

Copy `.mcp.json` into your project root (edit the backend URL for production):

```json
{
  "mcpServers": {
    "orqis": {
      "command": "orqis",
      "args": ["mcp", "--backend-url", "https://orqis-production.up.railway.app"],
      "env": { "ORQIS_ADMIN_TOKEN": "" }
    }
  }
}
```

| IDE / agent | Where to add the server |
|---|---|
| **Cursor / Windsurf / Claude Code** | Project `.mcp.json` (or user MCP config) |
| **VS Code** | Settings → MCP → add stdio server |
| **JetBrains / Zed / others** | MCP settings → command `orqis`, args `mcp --backend-url …` |

When `ORQIS_ADMIN_TOKEN` is set on the backend, put the same value in the MCP `env` block (or pass `--admin-token`) so approve/dismiss/open-PR tools work.

Tools exposed: `list_incidents`, `get_incident`, `get_incident_prompt`, `approve_incident`, `open_pr`, `resolve_incident`, `dismiss_incident`.

The dashboard **Settings** page also fetches `GET /integrations/ide-setup` with copy-paste snippets per IDE.

### Option B — Copy for AI assistant (no MCP)

On the dashboard, click **Copy for AI assistant** on any incident. Paste the prompt into VS Code Copilot Chat, Cursor, Claude Code, Windsurf, JetBrains AI, or any terminal agent. The text includes error context, code, and the suggested diff.

---

## How incidents work

```
log line arrives → pattern_matcher classifies (~0.1ms)
                 → fallback interpretation set instantly
                 → LLM interpretation replaces it (~500ms, non-blocking)
                 → if traceback: RCA pipeline fires
                     → file_reader extracts location + code context
                     → patch_generator generates unified diff
                     → incident status: OPEN → PATCHED
                     → dashboard + MCP see the incident
                     → you approve or dismiss
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `LLM_PROVIDER` | `ollama` | `ollama` (free, local) or `anthropic` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model to use with Ollama |
| `ORQIS_BACKEND_URL` | `http://localhost:8000` | Backend URL (used by daemon) |
| `ORQIS_DRAIN_TOKEN` | — | Auth token for `/drain` endpoint (leave unset for local dev) |
| `ORQIS_ADMIN_TOKEN` | — | Protects incident mutations and settings; pass to MCP `env` and dashboard Settings |
| `ORQIS_DEV_MODE` | `1` | Set `0` in production (enforces webhook signatures) |
