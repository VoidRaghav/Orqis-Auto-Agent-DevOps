import os
from dotenv import load_dotenv

load_dotenv()

# LLM provider for error interpretation: "anthropic" | "ollama"
# Use "ollama" for free local inference during development/demo
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

# Anthropic (paid). Patch generation always prefers Anthropic when a key is set,
# regardless of LLM_PROVIDER — patch correctness is what users pay for, and the
# per-patch cost is negligible next to the incident it resolves.
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
# Interpretation is a one-sentence summary — a small, fast model is plenty.
ANTHROPIC_INTERPRET_MODEL: str = os.getenv("ANTHROPIC_INTERPRET_MODEL", "claude-haiku-4-5")
# Patch + RCA generation is correctness-critical — use the strongest model.
ANTHROPIC_PATCH_MODEL: str = os.getenv("ANTHROPIC_PATCH_MODEL", "claude-opus-4-8")

# Ollama (free, local) — only used when LLM_PROVIDER=ollama
# Install: brew install ollama && ollama serve && ollama pull llama3.2:3b
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Redis for storing live event state
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# Postgres — system of record for tenants, API keys, users, GitHub installs, and
# the durable incident/audit history. When unset, the backend runs in
# single-tenant mode (no auth, one shared "default" workspace) for local dev.
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Multi-tenant mode is on whenever a database is configured. In this mode the
# ingest endpoints require a per-tenant API key and all state is scoped by it.
MULTI_TENANT: bool = bool(DATABASE_URL)

# GitHub OAuth (dashboard login). Distinct from the GitHub App credentials.
GITHUB_OAUTH_CLIENT_ID: str = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
GITHUB_OAUTH_CLIENT_SECRET: str = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")
# Signs dashboard session cookies. Required in production; dev falls back.
SESSION_SECRET: str = os.getenv("ORQIS_SESSION_SECRET", "orqis-dev-session-secret")

# URL of the Orqis backend server (daemon pushes events here)
BACKEND_URL: str = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")

# Keep interpretation short - one clear sentence is enough
LLM_MAX_TOKENS: int = 80

# Max events to keep in Redis (rolling window)
REDIS_EVENT_LIMIT: int = 1000

# Drain endpoint auth token.
# Set ORQIS_DRAIN_TOKEN to a long random string when deploying publicly.
# If empty, the /drain endpoint is open (fine for local dev, not for production).
DRAIN_TOKEN: str = os.getenv("ORQIS_DRAIN_TOKEN", "")

# Project root the RCA pipeline uses to locate source files from tracebacks.
# Captured once at startup so backend cwd changes can't break it.
PROJECT_ROOT: str = os.getenv("ORQIS_PROJECT_ROOT", os.getcwd())

# Allowed CORS origins for the dashboard (comma-separated). The browser blocks
# cross-origin REST calls without these headers. Defaults cover local dev; add
# your Vercel URL for production, or set "*" to allow any origin.
CORS_ORIGINS: str = os.getenv(
    "ORQIS_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)

# Sentry integration — shared secret used to verify webhook signatures.
# Found in Sentry: Settings -> Developer Settings -> your integration -> Client Secret.
# If empty, signature verification is skipped (fine for local dev, not production).
SENTRY_WEBHOOK_SECRET: str = os.getenv("ORQIS_SENTRY_SECRET", "")

# --- GitHub App integration ---------------------------------------------------
# Orqis opens fix PRs through a GitHub App the user installs on their repos.
# Create the app at: GitHub -> Settings -> Developer settings -> GitHub Apps.
# Permissions: Contents (read/write), Pull requests (write), Metadata (read).
# Subscribe to events: installation, installation_repositories, pull_request.
GITHUB_APP_ID: str = os.getenv("GITHUB_APP_ID", "")

# The app's PEM private key. Accept either the raw PEM contents (GITHUB_APP_PRIVATE_KEY,
# with literal \n escapes allowed) or a path to the .pem file (GITHUB_APP_PRIVATE_KEY_PATH).
GITHUB_APP_PRIVATE_KEY: str = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
GITHUB_APP_PRIVATE_KEY_PATH: str = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")

# Webhook shared secret — verifies the X-Hub-Signature-256 header on deliveries.
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# The app's URL slug — used to build the install URL https://github.com/apps/<slug>/installations/new
GITHUB_APP_SLUG: str = os.getenv("GITHUB_APP_SLUG", "")

# Public base URL of this Orqis backend (for webhook + post-install redirect links).
PUBLIC_URL: str = os.getenv("ORQIS_PUBLIC_URL", "http://localhost:8000")

# Admin token guarding settings mutations (PUT /settings/*). If empty, settings
# writes are open (fine for local dev only — set this in production).
ADMIN_TOKEN: str = os.getenv("ORQIS_ADMIN_TOKEN", "")

# Secret used to HMAC-sign outbound hot-reload callbacks so the user's app can
# verify the payload genuinely came from Orqis.
RELOAD_SECRET: str = os.getenv("ORQIS_RELOAD_SECRET", "")

# When false, security-sensitive endpoints reject unauthenticated requests even if
# ORQIS_ADMIN_TOKEN is unset, and GitHub webhooks require GITHUB_WEBHOOK_SECRET.
# Default true for local dev; set ORQIS_DEV_MODE=0 in production.
DEV_MODE: bool = os.getenv("ORQIS_DEV_MODE", "1").lower() in ("1", "true", "yes")