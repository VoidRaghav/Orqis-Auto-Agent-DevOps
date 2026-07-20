# Orqis product demo

Professional **full product walkthrough** with real browser clicks, broken test code, live log errors, dashboard interactions, GitHub repo linking, and the actual PR on your repo.

## Watch the recording

| File | Description |
|------|-------------|
| **[`orqis-full-product-demo.mp4`](./orqis-full-product-demo.mp4)** | **Main demo** — Playwright screen recording with clicks (~90s) |
| [`orqis-full-product-demo.webm`](./orqis-full-product-demo.webm) | Same video (WebM) |
| [`walkthrough.html`](./walkthrough.html) | Interactive step-through + older slideshow |
| **[`orqis-ide-full-demo.mp4`](./orqis-ide-full-demo.mp4)** | **IDE + dashboard** — Cursor UI, install, MCP, live dashboard, Apply Fix |
| [`orqis-ide-full-demo.webm`](./orqis-ide-full-demo.webm) | Same IDE demo (WebM) |

**Replay VIP / investor demo:**
```powershell
Start-Process demo\recording\orqis-vip-investor-demo.mp4
```

**Re-record VIP demo** (landing → onboarding → IDE → dashboard Apply Fix):
```powershell
docker start orqis-redis-stress   # or Redis on REDIS_URL
python scripts/record_vip_investor_demo.py
```

| File | Description |
|------|-------------|
| **[`orqis-vip-investor-demo.mp4`](./orqis-vip-investor-demo.mp4)** | **VC/VIP cut** — landing, GitHub wizard, IDE/MCP, live detect & Apply Fix |
| **[`orqis-full-product-demo.mp4`](./orqis-full-product-demo.mp4)** | **Main demo** — Playwright screen recording with clicks (~90s) |
| [`orqis-full-product-demo.webm`](./orqis-full-product-demo.webm) | Same video (WebM) |
| [`walkthrough.html`](./walkthrough.html) | Interactive step-through + older slideshow |
| **[`orqis-ide-full-demo.mp4`](./orqis-ide-full-demo.mp4)** | **IDE + dashboard** — Cursor UI, install, MCP, live dashboard, Apply Fix |
| [`orqis-ide-full-demo.webm`](./orqis-ide-full-demo.webm) | Same IDE demo (WebM) |

Live PR: https://github.com/Siddarthb07/orqis-e2e-test/pull/1

## Re-record

```bash
docker start orqis-redis
# backend + frontend running on :8000 / :3000
python scripts/record_full_product_demo.py
```
