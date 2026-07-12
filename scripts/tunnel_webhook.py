#!/usr/bin/env python3
"""Start cloudflared tunnel and print webhook URL for local GitHub App dev."""

import argparse
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description="Tunnel Orqis webhooks via cloudflared")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{args.port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        print("cloudflared not found — install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        return 1
    print(f"Starting tunnel to localhost:{args.port} …")
    for _ in range(60):
        line = proc.stdout.readline() if proc.stdout else ""
        if "trycloudflare.com" in line or "https://" in line:
            for token in line.split():
                if token.startswith("https://") and "trycloudflare" in token:
                    base = token.rstrip("/")
                    print(f"\nPublic URL: {base}")
                    print(f"Webhook:    {base}/integrations/github/webhook")
                    print(f"Set ORQIS_PUBLIC_URL={base} in .env")
                    proc.wait()
                    return 0
        time.sleep(0.2)
    print("Timed out waiting for tunnel URL")
    proc.kill()
    return 1


if __name__ == "__main__":
    sys.exit(main())
