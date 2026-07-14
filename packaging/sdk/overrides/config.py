"""
Orqis SDK configuration.

The client only needs two things: where to send events, and the API key that
routes them to your workspace. Both can come from the environment or be passed
directly to orqis.init(). This slim module intentionally replaces the full
backend config so no server-side settings are shipped to users.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Orqis backend that receives traces. Override with orqis.init(backend_url=...)
# or the ORQIS_BACKEND_URL env var to point at a self-hosted deployment.
BACKEND_URL: str = os.getenv(
    "ORQIS_BACKEND_URL", "https://orqis-auto-agent-devops.onrender.com"
)

# Workspace ingest API key. Override with orqis.init(api_key=...) or ORQIS_API_KEY.
INGEST_API_KEY: str = os.getenv("ORQIS_API_KEY", "")
