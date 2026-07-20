"""Local benchmarks + burst stress for Orqis (not CI).

Usage (with backend + Redis already up, env from .env.stress):
  python scripts/bench_stress.py
"""
from __future__ import annotations

import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

BASE = os.environ.get("ORQIS_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
TOKEN = os.environ.get("ORQIS_ADMIN_TOKEN", "").strip()
ROOT = os.environ.get(
    "ORQIS_PROJECT_ROOT",
    os.path.join(os.path.dirname(__file__), "..", "test-agent"),
)
LOC = os.path.normpath(os.path.join(ROOT, "src", "refund_agent.py")).replace("\\", "/") + ":1:resolve_refund"


def pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, max(0, int(len(sorted_vals) * p)))
    return sorted_vals[i]


def bench_endpoint(client: httpx.Client, method: str, path: str, *, n: int = 50, **kwargs) -> dict:
    times: list[float] = []
    errors = 0
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            resp = client.request(method, path, **kwargs)
            if resp.status_code >= 400:
                errors += 1
        except Exception:
            errors += 1
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "n": n,
        "errors": errors,
        "p50_ms": round(pct(times, 0.50), 2),
        "p95_ms": round(pct(times, 0.95), 2),
        "p99_ms": round(pct(times, 0.99), 2),
        "mean_ms": round(statistics.mean(times), 2),
        "max_ms": round(times[-1], 2),
    }


def burst_trace(client: httpx.Client, *, n: int = 200, workers: int = 32) -> dict:
    headers = {"X-Orqis-Admin-Token": TOKEN} if TOKEN else {}
    client.post("/demo/reset", params={"clear": "true"}, headers=headers).raise_for_status()

    latencies: list[float] = []
    errors = 0
    start = time.perf_counter()

    def one(i: int) -> tuple[int, float]:
        t0 = time.perf_counter()
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": "tool.start",
            "provider": "langchain",
            "run_id": str(uuid.uuid4()),
            "model": "gpt-4o",
            "tool_name": "check_order_status",
            "tool_args": '{"order_id": "1042"}',
            "code_location": LOC,
            "cost_usd": 0.01,
            "source": f"bench-{i % 8}",
        }
        resp = client.post("/trace", json=event)
        return resp.status_code, (time.perf_counter() - t0) * 1000

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, i) for i in range(n)]
        for f in as_completed(futs):
            code, dt = f.result()
            latencies.append(dt)
            if code >= 400:
                errors += 1

    elapsed = time.perf_counter() - start
    latencies.sort()
    health = client.get("/health").json()
    return {
        "posts": n,
        "workers": workers,
        "elapsed_s": round(elapsed, 3),
        "rps": round(n / elapsed, 1),
        "http_errors": errors,
        "p50_ms": round(pct(latencies, 0.50), 2),
        "p95_ms": round(pct(latencies, 0.95), 2),
        "p99_ms": round(pct(latencies, 0.99), 2),
        "max_ms": round(latencies[-1], 2),
        "health": health,
    }


def main() -> int:
    print(f"target={BASE}")
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print(f"health={health.json()}")

        print("\n==> sequential latency benchmarks (n=50)")
        for label, method, path, kwargs in [
            ("GET /health", "GET", "/health", {}),
            ("GET /incidents?limit=20", "GET", "/incidents", {"params": {"limit": 20}}),
            ("GET /health/ready", "GET", "/health/ready", {}),
        ]:
            try:
                stats = bench_endpoint(client, method, path, **kwargs)
                print(f"{label}: {stats}")
            except Exception as exc:
                print(f"{label}: SKIP ({exc})")

        print("\n==> burst POST /trace (200 posts, 32 workers)")
        burst = burst_trace(client, n=200, workers=32)
        print(burst)

        print("\n==> heavier burst POST /trace (500 posts, 48 workers)")
        burst2 = burst_trace(client, n=500, workers=48)
        print(burst2)

        # Final health after stress
        final = client.get("/health").json()
        print(f"\nfinal_health={final}")
        if burst["http_errors"] or burst2["http_errors"]:
            print("RESULT: FAIL (http errors under burst)")
            return 1
        if final.get("status") != "ok":
            print("RESULT: FAIL (health not ok)")
            return 1
        print("RESULT: PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
