#!/usr/bin/env python3
"""
Resilient GitHub App registration via the manifest flow.

Runs a local callback server that, the instant GitHub redirects back with the
one-time manifest code, exchanges it for app credentials and writes them to
disk. Designed to run in the background so an interrupted foreground shell can
never lose the code. Progress is written to secrets/app_setup_status.json.
"""

import base64
import json
import pathlib
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEC = ROOT / "secrets"
SEC.mkdir(exist_ok=True)
STATUS = SEC / "app_setup_status.json"
ENV_PATH = SEC / "orqis-github-app.env"
PEM_PATH = SEC / "orqis-github-app.pem"

MANIFEST_PORT = 9999
MANIFEST_CALLBACK = f"http://localhost:{MANIFEST_PORT}/manifest-callback"

MANIFEST = {
    "name": "Orqis E2E Test " + secrets.token_hex(2),
    "url": "http://localhost:8000",
    # No hook_attributes: GitHub rejects localhost webhook URLs. Orqis records
    # the installation via the setup redirect and reconciles merged PRs by
    # polling (poll_open_prs), so no inbound webhook is required for this test.
    "hook_attributes": {"active": False},
    "redirect_url": MANIFEST_CALLBACK,
    "setup_url": "http://localhost:8000/integrations/github/callback",
    "callback_urls": ["http://localhost:8000/integrations/github/callback"],
    "setup_on_update": True,
    "public": False,
    "default_permissions": {
        "contents": "write",
        "metadata": "read",
        "pull_requests": "write",
    },
    "default_events": [],
}


def write_status(**kw):
    STATUS.write_text(json.dumps(kw, indent=2), encoding="utf-8")


def convert(code: str) -> dict:
    resp = httpx.post(
        f"https://api.github.com/app-manifests/{code}/conversions",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        code = (qs.get("code") or [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"missing code")
            return
        try:
            data = convert(code)
            app_id = data["id"]
            slug = data["slug"]
            PEM_PATH.write_text(data["pem"], encoding="utf-8")
            webhook_secret = data.get("webhook_secret") or ""
            env_lines = [
                f"GITHUB_APP_ID={app_id}",
                f"GITHUB_APP_SLUG={slug}",
                f"GITHUB_APP_PRIVATE_KEY_PATH={PEM_PATH}",
                f"GITHUB_WEBHOOK_SECRET={webhook_secret}",
                "ORQIS_PUBLIC_URL=http://localhost:8000",
                "ORQIS_DEV_MODE=1",
            ]
            ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            write_status(
                state="done",
                app_id=app_id,
                slug=slug,
                html_url=data.get("html_url"),
                install_url=f"https://github.com/apps/{slug}/installations/new",
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>Orqis GitHub App created.</h2>"
                b"<p>Credentials saved. You can close this tab and return to the agent.</p>"
            )
        except Exception as e:  # noqa: BLE001
            write_status(state="error", error=str(e))
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"conversion failed: {e}".encode())


def main() -> int:
    if ENV_PATH.is_file() and PEM_PATH.is_file():
        try:
            st = json.loads(STATUS.read_text(encoding="utf-8"))
            if st.get("state") == "done":
                print("GitHub App already registered — see secrets/orqis-github-app.env", flush=True)
                print("Delete secrets/ to re-register, or run scripts/tunnel_webhook.py for webhooks.", flush=True)
                return 0
        except Exception:
            pass

    manifest_b64 = (
        base64.urlsafe_b64encode(json.dumps(MANIFEST).encode()).decode().rstrip("=")
    )
    register_url = (
        f"https://github.com/settings/apps/new?state=orqis-e2e&manifest={manifest_b64}"
    )

    write_status(state="waiting", register_url=register_url)
    print("REGISTER_URL:", register_url, flush=True)

    server = HTTPServer(("127.0.0.1", MANIFEST_PORT), Handler)
    try:
        webbrowser.open(register_url)
    except Exception:
        pass

    # Serve until the callback writes a terminal status, then a couple extra
    # requests are harmless. Handle requests until 'done'/'error'.
    while True:
        server.handle_request()
        try:
            st = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception:
            continue
        if st.get("state") in ("done", "error"):
            print("FINAL_STATE:", st.get("state"), flush=True)
            return 0 if st.get("state") == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
