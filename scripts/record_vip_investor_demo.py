#!/usr/bin/env python3
"""
VC / VIP investor demo — professional full-product walkthrough.

Narrative arc:
  1. Title + value prop
  2. Landing page (live)
  3. GitHub onboarding wizard (Settings)
  4. IDE / MCP install story (HTML scenes)
  5. Live dashboard — detect RUNAWAY_LOOP, diff, Apply Fix
  6. Changes + Activity + AI calls
  7. Closing card (PR-first self-healing)

Outputs:
  demo/recording/orqis-vip-investor-demo.webm
  demo/recording/orqis-vip-investor-demo.mp4

Usage:
  # Redis on :6380 (or REDIS_URL), then:
  python scripts/record_vip_investor_demo.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers import (  # noqa: E402
    reset_orqis,
    reset_test_agent,
    trigger_runaway_traces,
    wait_for_patched_incident,
)

OUT_DIR = ROOT / "demo" / "recording"
VIP_SCENES = OUT_DIR / "vip-scenes"
IDE_SCENES = OUT_DIR / "scenes" / "ide"
VIDEO_DIR = OUT_DIR / "pw-videos-vip"
FRONTEND_DIR = ROOT / "frontend"

BACKEND_PORT = int(os.getenv("ORQIS_VIP_BACKEND_PORT", "8030"))
FRONTEND_PORT = int(os.getenv("ORQIS_VIP_FRONTEND_PORT", "3020"))
BACKEND = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND = f"http://127.0.0.1:{FRONTEND_PORT}"
ADMIN_TOKEN = os.getenv(
    "ORQIS_ADMIN_TOKEN", "vipdemo00000000000000000000000000001"
)
PROJECT_ROOT = Path(
    os.getenv("ORQIS_PROJECT_ROOT", str(ROOT / "test-agent"))
).resolve()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")


VIP_CARDS = {
    "00-title.html": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html,body{margin:0;height:100%;background:#07090f;color:#e8ecf4;
  font-family:"Segoe UI",system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
  .wrap{text-align:center;max-width:920px;padding:48px}
  .brand{font-size:14px;letter-spacing:.28em;text-transform:uppercase;color:#7dd3c0;margin-bottom:28px}
  h1{font-size:64px;font-weight:600;margin:0 0 18px;letter-spacing:-.03em}
  p{font-size:22px;line-height:1.45;color:#9aa3b5;margin:0 auto;max-width:640px}
  .bar{width:72px;height:3px;background:linear-gradient(90deg,#3ddc97,#5b8def);margin:32px auto}
</style></head><body><div class="wrap">
  <div class="brand">Orqis</div>
  <h1>Self-healing ops<br>for AI agents</h1>
  <div class="bar"></div>
  <p>Detect silent failures. Generate verified patches. Open reviewable PRs — never push to main.</p>
</div></body></html>""",
    "01-problem.html": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html,body{margin:0;height:100%;background:#07090f;color:#e8ecf4;
  font-family:"Segoe UI",system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
  .wrap{max-width:880px;padding:48px}
  .eyebrow{color:#f0a060;letter-spacing:.2em;text-transform:uppercase;font-size:13px;margin-bottom:20px}
  h1{font-size:42px;margin:0 0 24px;font-weight:600}
  ul{margin:0;padding:0;list-style:none}
  li{font-size:20px;color:#9aa3b5;padding:12px 0;border-bottom:1px solid #1a2030}
  li span{color:#e8ecf4}
</style></head><body><div class="wrap">
  <div class="eyebrow">The gap</div>
  <h1>AI agents fail silently</h1>
  <ul>
    <li><span>Runaway tool loops</span> — no traceback, just a burning bill</li>
    <li><span>Corrupt tool output</span> — empty payloads consumed as truth</li>
    <li><span>Retry storms &amp; cost spikes</span> — correct answers, wrong economics</li>
  </ul>
</div></body></html>""",
    "08-close.html": """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html,body{margin:0;height:100%;background:#07090f;color:#e8ecf4;
  font-family:"Segoe UI",system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
  .wrap{text-align:center;max-width:900px;padding:48px}
  .brand{font-size:14px;letter-spacing:.28em;text-transform:uppercase;color:#7dd3c0;margin-bottom:24px}
  h1{font-size:48px;font-weight:600;margin:0 0 20px}
  p{font-size:20px;color:#9aa3b5;line-height:1.5;margin:0}
  .pill{display:inline-block;margin-top:36px;padding:12px 22px;border:1px solid #2a3348;
  border-radius:999px;font-size:14px;color:#7dd3c0;letter-spacing:.06em}
</style></head><body><div class="wrap">
  <div class="brand">Orqis</div>
  <h1>Detect → Patch → PR → Merge</h1>
  <p>Production-grade self-healing for agent workloads.<br>
  Human always reviews. Default branch stays untouched.</p>
  <div class="pill">orqis.dev · GitHub App · MCP · Multi-tenant ready</div>
</div></body></html>""",
}


def write_vip_scenes() -> None:
    VIP_SCENES.mkdir(parents=True, exist_ok=True)
    for name, html in VIP_CARDS.items():
        (VIP_SCENES / name).write_text(html, encoding="utf-8")


def backend_env() -> dict[str, str]:
    cors = f"http://127.0.0.1:{FRONTEND_PORT},http://localhost:{FRONTEND_PORT}"
    env = os.environ.copy()
    env.update(
        {
            "ORQIS_PROJECT_ROOT": str(PROJECT_ROOT),
            "ORQIS_ADMIN_TOKEN": ADMIN_TOKEN,
            "REDIS_URL": REDIS_URL,
            "ORQIS_BACKEND_URL": BACKEND,
            "ORQIS_PUBLIC_URL": BACKEND,
            "ORQIS_CORS_ORIGINS": cors,
            "ORQIS_DEV_MODE": "1",
            "ORQIS_MULTI_TENANT": "0",
            "ORQIS_HOSTED": "0",
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "ollama"),
        }
    )
    return env


def wait_http(url: str, timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5.0).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(url)


def wait_orqis(timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            h = httpx.get(f"{BACKEND}/health", timeout=5.0)
            if h.status_code == 200 and h.json().get("status") == "ok":
                if httpx.get(f"{BACKEND}/incidents?limit=1", timeout=5.0).status_code == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(BACKEND)


def start_backend() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "orqis.cli", "start", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        cwd=str(ROOT),
        env=backend_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_frontend() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "VITE_API_URL": BACKEND,
            "VITE_WS_URL": f"ws://127.0.0.1:{BACKEND_PORT}/ws",
        }
    )
    env.pop("VITE_MULTI_TENANT", None)
    return subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)],
        cwd=str(FRONTEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=os.name == "nt",
    )


def seed_incident() -> dict:
    # helpers.admin_token() reads ORQIS_ADMIN_TOKEN from the process env
    os.environ["ORQIS_ADMIN_TOKEN"] = ADMIN_TOKEN
    os.environ["ORQIS_BACKEND_URL"] = BACKEND
    os.environ["ORQIS_PROJECT_ROOT"] = str(PROJECT_ROOT)
    reset_test_agent(PROJECT_ROOT)
    with httpx.Client(base_url=BACKEND, timeout=30.0) as client:
        tid = str(uuid.uuid4())
        reset_orqis(client, tid)
        trigger_runaway_traces(client, PROJECT_ROOT, tid)
        return wait_for_patched_incident(client)


def to_mp4(webm: Path, mp4: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise RuntimeError("ffmpeg not found") from exc
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(webm),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-crf",
            "18",
            "-preset",
            "medium",
            str(mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def record(incident: dict) -> Path:
    from playwright.sync_api import sync_playwright

    write_vip_scenes()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_ide_demo_scenes.py")],
        cwd=str(ROOT),
        check=False,
    )

    if VIDEO_DIR.exists():
        shutil.rmtree(VIDEO_DIR, ignore_errors=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=280)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.25,
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()

        def card(name: str, ms: int = 4200) -> None:
            page.goto((VIP_SCENES / name).resolve().as_uri(), wait_until="domcontentloaded")
            page.wait_for_timeout(ms)

        def ide(name: str, ms: int = 5500) -> None:
            path = IDE_SCENES / name
            if path.is_file():
                page.goto(path.resolve().as_uri(), wait_until="domcontentloaded")
                page.wait_for_timeout(ms)

        # 1–2 Title / problem
        card("00-title.html", 5000)
        card("01-problem.html", 5500)

        # 3 Landing
        page.goto(f"{FRONTEND}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4500)
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(2500)
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(2000)

        # 4 Onboarding / Settings wizard
        page.goto(f"{FRONTEND}/settings", wait_until="domcontentloaded", timeout=60000)
        page.evaluate(
            "(t) => localStorage.setItem('orqis_admin_token', t)",
            ADMIN_TOKEN,
        )
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if page.get_by_text("GitHub setup").count():
            page.get_by_text("GitHub setup").first.scroll_into_view_if_needed()
            page.wait_for_timeout(3500)
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(2500)
        if page.get_by_role("button", name="Verify setup").count():
            page.get_by_role("button", name="Verify setup").first.click()
            page.wait_for_timeout(2500)

        # 5 IDE narrative
        for name in [
            "00-intro.html",
            "01-ide-buggy.html",
            "02-install.html",
            "03-mcp.html",
            "04-agent-run.html",
        ]:
            ide(name, 6000 if "04" in name or "01" in name else 5000)

        # 6 Live dashboard — detect & fix
        page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=60000)
        page.evaluate(
            "(t) => localStorage.setItem('orqis_admin_token', t)",
            ADMIN_TOKEN,
        )
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        for label in ("Issues", "Issues & Fixes"):
            btn = page.get_by_role("button", name=label)
            if btn.count():
                btn.first.click()
                break
        page.wait_for_timeout(1500)

        for _ in range(40):
            if page.get_by_text("RUNAWAY_LOOP").count() or page.get_by_text("PATCHED").count():
                break
            page.wait_for_timeout(400)

        if page.get_by_text("RUNAWAY_LOOP").count():
            page.get_by_text("RUNAWAY_LOOP").first.click()
            page.wait_for_timeout(1200)
        if page.get_by_text("PATCHED").count():
            page.get_by_text("PATCHED").first.click()
            page.wait_for_timeout(2800)

        if page.get_by_text("SUGGESTED FIX").count():
            page.get_by_text("SUGGESTED FIX").first.scroll_into_view_if_needed()
            page.wait_for_timeout(2500)

        apply_btn = page.get_by_role("button", name="Apply Fix →")
        if apply_btn.count() == 0:
            apply_btn = page.get_by_role("button", name="Apply Fix")
        if apply_btn.count():
            apply_btn.first.click()
            page.wait_for_timeout(4000)

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_ide_demo_scenes.py")],
            cwd=str(ROOT),
            check=False,
        )

        for label, wait in (("Changes", 3200), ("AI calls", 2800), ("Activity", 2800)):
            btn = page.get_by_role("button", name=label)
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(wait)

        # 7 Fixed IDE + close
        ide("06-ide-fixed.html", 5500)
        card("08-close.html", 5500)

        page.close()
        context.close()
        browser.close()

    webms = sorted(VIDEO_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not webms:
        raise RuntimeError("no webm recorded")
    dest_webm = OUT_DIR / "orqis-vip-investor-demo.webm"
    dest_mp4 = OUT_DIR / "orqis-vip-investor-demo.mp4"
    shutil.copy2(webms[0], dest_webm)
    to_mp4(dest_webm, dest_mp4)
    return dest_mp4


def main() -> int:
    write_vip_scenes()
    print(f"[vip] backend={BACKEND} frontend={FRONTEND} redis={REDIS_URL}")

    # Prefer existing redis; try ping
    try:
        import redis

        redis.from_url(REDIS_URL).ping()
    except Exception as exc:
        print(f"[vip] Redis not reachable at {REDIS_URL}: {exc}")
        print("[vip] Start: docker run -d --name orqis-redis-stress -p 6380:6379 redis:7-alpine")
        return 1

    be = fe = None
    try:
        be = start_backend()
        wait_orqis()
        print("[vip] backend ready")
        fe = start_frontend()
        wait_http(FRONTEND, timeout_s=120)
        print("[vip] frontend ready")

        incident = seed_incident()
        print(f"[vip] seeded incident status={incident.get('status')} id={incident.get('id')}")

        out = record(incident)
        print(f"[vip] wrote {out}")
        print(f"[vip] also {OUT_DIR / 'orqis-vip-investor-demo.webm'}")
        return 0
    finally:
        for proc in (fe, be):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except Exception:
                    proc.kill()
        reset_test_agent(PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
