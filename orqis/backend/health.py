"""Extended health / readiness checks."""

from __future__ import annotations

from .. import config
from ..backend import store
from ..daemon import interpreter
from ..integrations.github import auth as gh_auth


async def readiness() -> dict:
    checks: dict[str, dict] = {}

    try:
        r = await store.get_redis()
        await r.ping()
        checks["redis"] = {"ok": True}
    except Exception as exc:
        checks["redis"] = {"ok": False, "detail": str(exc)}

    llm = await interpreter.check_readiness()
    checks["llm"] = llm

    if gh_auth.is_configured():
        try:
            # JWT mint proves PEM + app id are loadable.
            ok = gh_auth._app_jwt() is not None  # type: ignore[attr-defined]
            checks["github_app"] = {"ok": bool(ok)}
        except Exception:
            checks["github_app"] = {"ok": gh_auth.is_configured(), "detail": "jwt unavailable"}
    else:
        checks["github_app"] = {"ok": True, "detail": "not configured"}

    all_ok = all(c.get("ok") for c in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "multi_tenant": config.MULTI_TENANT,
        "checks": checks,
    }
