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