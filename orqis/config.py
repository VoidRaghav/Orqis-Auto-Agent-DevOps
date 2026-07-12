import os
from dotenv import load_dotenv

load_dotenv()

# LLM provider: "anthropic" | "ollama"
# Use "ollama" for free local inference during development/demo
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

# Anthropic (paid) — only used when LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"

# Ollama (free, local) — only used when LLM_PROVIDER=ollama
# Install: brew install ollama && ollama serve && ollama pull llama3.2:3b
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Redis for storing live event state
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

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

# Admin token guarding write paths (incident actions, PUT /settings). Required
# for dogfood and production — write endpoints return 401 when unset.
ADMIN_TOKEN: str = os.getenv("ORQIS_ADMIN_TOKEN", "")

# CI harness flags — block force=true approve overrides unless explicitly allowed.
CI_MODE: bool = os.getenv("ORQIS_CI", "").lower() in ("1", "true", "yes")
ALLOW_FORCE: bool = os.getenv("ORQIS_ALLOW_FORCE", "").lower() in ("1", "true", "yes")

# Secret used to HMAC-sign outbound hot-reload callbacks so the user's app can
# verify the payload genuinely came from Orqis.
RELOAD_SECRET: str = os.getenv("ORQIS_RELOAD_SECRET", "")

# When false, security-sensitive endpoints reject unauthenticated requests even if
# ORQIS_ADMIN_TOKEN is unset, and GitHub webhooks require GITHUB_WEBHOOK_SECRET.
# Default true for local dev; set ORQIS_DEV_MODE=0 in production.
DEV_MODE: bool = os.getenv("ORQIS_DEV_MODE", "1").lower() in ("1", "true", "yes")

# Multi-tenant hosted mode: per-workspace isolation, session + API-key auth.
# Default off — local single-tenant uses workspace "default" with no login.
MULTI_TENANT: bool = os.getenv("ORQIS_MULTI_TENANT", "0").lower() in ("1", "true", "yes")

# Hosted SKU: disable local-disk patch apply (PR-only fixes).
HOSTED: bool = os.getenv("ORQIS_HOSTED", "0").lower() in ("1", "true", "yes")

# --- Dashboard session (GitHub OAuth) -----------------------------------------
GITHUB_OAUTH_CLIENT_ID: str = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
GITHUB_OAUTH_CLIENT_SECRET: str = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")
SESSION_SECRET: str = os.getenv(
    "ORQIS_SESSION_SECRET",
    os.getenv("ORQIS_ADMIN_TOKEN", "") or "orqis-dev-session-change-me",
)
SESSION_COOKIE_NAME: str = os.getenv("ORQIS_SESSION_COOKIE", "orqis_session")
SESSION_COOKIE_SECURE: bool = os.getenv("ORQIS_SESSION_SECURE", "0").lower() in (
    "1",
    "true",
    "yes",
)

# Per-workspace ingest rate limit (requests per minute). 0 = unlimited.
INGEST_RATE_LIMIT_PER_MIN: int = int(os.getenv("ORQIS_INGEST_RATE_LIMIT", "600") or "600")

# Max request body size for ingest/drain (bytes). 0 = unlimited.
MAX_INGEST_BODY_BYTES: int = int(os.getenv("ORQIS_MAX_INGEST_BODY_BYTES", "2097152") or "2097152")

# Set at runtime by orqis.init() — sent as Bearer on trace POSTs
INGEST_API_KEY: str = os.getenv("ORQIS_API_KEY", "")


def validate_multi_tenant_startup() -> None:
    """Fail fast when multi-tenant production config is unsafe."""
    if not MULTI_TENANT:
        return
    weak_secrets = {
        "",
        "orqis-dev-session-change-me",
        ADMIN_TOKEN,
    }
    if len(SESSION_SECRET) < 32 or SESSION_SECRET in weak_secrets:
        msg = (
            "[orqis] ORQIS_SESSION_SECRET must be a random string of at least 32 "
            "characters when ORQIS_MULTI_TENANT=1"
        )
        if DEV_MODE:
            print(f"{msg} (allowed in dev mode only)")
        else:
            raise RuntimeError(msg)
    if not DEV_MODE:
        if not GITHUB_OAUTH_CLIENT_ID or not GITHUB_OAUTH_CLIENT_SECRET:
            raise RuntimeError(
                "[orqis] GITHUB_OAUTH_CLIENT_ID and GITHUB_OAUTH_CLIENT_SECRET are "
                "required when ORQIS_MULTI_TENANT=1 and ORQIS_DEV_MODE=0"
            )
        if HOSTED and not SESSION_COOKIE_SECURE:
            raise RuntimeError(
                "[orqis] ORQIS_SESSION_SECURE=1 is required when ORQIS_HOSTED=1"
            )
        if HOSTED and ADMIN_TOKEN:
            raise RuntimeError(
                "[orqis] ORQIS_ADMIN_TOKEN must not be set when ORQIS_HOSTED=1 "
                "(use per-workspace session auth only)"
            )