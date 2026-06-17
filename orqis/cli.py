"""
Orqis unified CLI.

Commands:
  orqis start             Start the backend server (Redis must be running)
  orqis monitor           Read logs from stdin or a file, stream to backend
  orqis incidents         Show active incidents with diffs — approve or dismiss
  orqis mcp               Start the MCP server (any MCP-compatible IDE)
  orqis status            Check backend health

Quick start (two terminals):
  Terminal 1:  orqis start
  Terminal 2:  python test_stream.py --loop | orqis monitor --source my-app
  Then:        orqis incidents      (in any terminal, anytime)

Railway setup (no local daemon needed — Railway pushes logs to Orqis):
  Settings → Log Drains → HTTP → https://your-orqis/drain?source=my-app
"""

import argparse
import os
import sys


# ANSI colours
_R  = "\033[31m"       # red
_Y  = "\033[33m"       # yellow
_G  = "\033[32m"       # green
_C  = "\033[36m"       # cyan
_B  = "\033[1m"        # bold
_DIM = "\033[2m"       # dim
_RST = "\033[0m"       # reset


def _cmd_start(args: argparse.Namespace) -> None:
    import uvicorn

    print(f"[orqis] starting backend on {args.host}:{args.port}", file=sys.stderr)
    uvicorn.run(
        "orqis.backend.server:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


def _cmd_monitor(args: argparse.Namespace) -> None:
    import asyncio

    from orqis.daemon import log_reader

    async def _run() -> None:
        if args.file:
            print(f"[orqis] tailing {args.file} (source={args.source})", file=sys.stderr)
            await log_reader.tail_file(args.file, source=args.source)
        else:
            print(f"[orqis] reading stdin (source={args.source})", file=sys.stderr)
            await log_reader.read_stdin(source=args.source)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n[orqis] monitor stopped", file=sys.stderr)


def _admin_headers() -> dict:
    import os

    token = os.getenv("ORQIS_ADMIN_TOKEN", "")
    return {"X-Orqis-Admin-Token": token} if token else {}


def _cmd_incidents(args: argparse.Namespace) -> None:
    """
    Interactive terminal incident browser.

    Lists open/patched incidents. For each incident with a diff:
      - shows the error, interpretation, file location, and unified diff
      - prompts: [a]pprove  [d]ismiss  [s]kip  [q]uit
    """
    import httpx

    base = args.backend_url
    try:
        r = httpx.get(f"{base}/incidents", params={"limit": 50}, timeout=10.0)
        r.raise_for_status()
    except Exception as e:
        print(f"{_R}[orqis] cannot reach backend at {base}: {e}{_RST}", file=sys.stderr)
        sys.exit(1)

    incidents = r.json()
    if not incidents:
        print("[orqis] no incidents found.")
        return

    # Filter to open/patched unless --all is passed
    if not args.all:
        incidents = [i for i in incidents if i.get("status") in ("open", "patched")]

    if not incidents:
        print(f"{_G}[orqis] no open incidents.{_RST}")
        return

    print(f"\n{_B}Orqis Incidents{_RST}  ({len(incidents)} shown)\n")

    for inc in incidents:
        _print_incident(inc)

        status = inc.get("status", "open")
        has_diff = bool(inc.get("diff"))

        if status in ("approved", "dismissed"):
            print(f"  {_DIM}[{status}]{_RST}\n")
            continue

        # Build prompt based on what's available
        if has_diff:
            prompt_choices = "[a]pprove  [d]ismiss  [s]kip  [q]uit"
        else:
            prompt_choices = "[d]ismiss  [s]kip  [q]uit  (no patch available yet)"

        try:
            choice = input(f"  {_B}>{_RST} {prompt_choices}  ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_RST}[orqis] exiting")
            return

        if choice == "q":
            return
        elif choice == "a" and has_diff:
            try:
                res = httpx.post(
                    f"{base}/incidents/{inc['id']}/approve",
                    headers=_admin_headers(),
                    timeout=15.0,
                )
                if res.status_code == 200:
                    data = res.json()
                    print(f"  {_G}Patch applied to {data.get('file', 'file')}{_RST}")
                else:
                    print(f"  {_R}Approve failed: {res.json().get('detail', res.status_code)}{_RST}")
            except Exception as e:
                print(f"  {_R}Error: {e}{_RST}")
        elif choice == "d":
            try:
                httpx.post(
                    f"{base}/incidents/{inc['id']}/dismiss",
                    headers=_admin_headers(),
                    timeout=10.0,
                )
                print(f"  {_DIM}Dismissed.{_RST}")
            except Exception as e:
                print(f"  {_R}Error: {e}{_RST}")
        else:
            print(f"  {_DIM}Skipped.{_RST}")

        print()


def _print_incident(inc: dict) -> None:
    status = inc.get("status", "open")
    status_colour = {
        "open": _Y,
        "patched": _C,
        "approved": _G,
        "dismissed": _DIM,
    }.get(status, "")

    hits = inc.get("hit_count", 1)
    hit_str = f"  {_R}x{hits}{_RST}" if hits > 1 else ""
    err_type = f"[{inc['error_type']}]" if inc.get("error_type") else ""
    fp = inc.get("file_path") or ""
    line = inc.get("error_line") or ""
    loc = f"  {_DIM}{fp}:{line}{_RST}" if fp else ""

    print(f"{status_colour}{_B}[{status.upper()}]{_RST}{hit_str}  {err_type}{loc}")
    print(f"  {inc.get('error_message', '')[:120]}")
    if inc.get("interpretation"):
        print(f"  {_C}{inc['interpretation']}{_RST}")
    if inc.get("code_context"):
        fn = inc.get("function_name", "")
        start = inc.get("context_start_line", 1)
        print(f"\n  {_DIM}Function: {fn}  (line {start}){_RST}")
        for i, cl in enumerate(inc["code_context"].splitlines()):
            lineno = start + i
            marker = f"{_R}>{_RST}" if lineno == inc.get("error_line") else " "
            print(f"  {_DIM}{lineno:4d}{_RST} {marker} {cl}")
    if inc.get("diff"):
        print(f"\n  {_B}Suggested diff:{_RST}")
        for dl in inc["diff"].splitlines():
            if dl.startswith("+") and not dl.startswith("+++"):
                print(f"  {_G}{dl}{_RST}")
            elif dl.startswith("-") and not dl.startswith("---"):
                print(f"  {_R}{dl}{_RST}")
            else:
                print(f"  {_DIM}{dl}{_RST}")
    print()


def _cmd_mcp(args: argparse.Namespace) -> None:
    from orqis.mcp.server import run

    run(backend_url=args.backend_url, admin_token=args.admin_token)


def _cmd_status(args: argparse.Namespace) -> None:
    import httpx

    url = f"{args.backend_url}/health"
    try:
        r = httpx.get(url, timeout=5.0)
        data = r.json()
        print(f"{_G}[orqis] backend OK{_RST} — ws_clients={data.get('ws_clients', 0)}")
    except Exception as e:
        print(f"{_R}[orqis] backend unreachable at {url}: {e}{_RST}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="orqis",
        description="Orqis — autonomous self-healing ops",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # --- start ---
    p_start = sub.add_parser("start", help="start the Orqis backend server")
    p_start.add_argument("--host", default="0.0.0.0")
    p_start.add_argument("--port", type=int, default=8000)
    p_start.set_defaults(func=_cmd_start)

    # --- monitor ---
    p_mon = sub.add_parser("monitor", help="stream logs to the Orqis backend")
    p_mon.add_argument("--file", metavar="PATH", help="tail a log file (default: stdin)")
    p_mon.add_argument("--source", default="unknown", help="label shown on dashboard")
    p_mon.set_defaults(func=_cmd_monitor)

    # --- incidents ---
    p_inc = sub.add_parser("incidents", help="review incidents and apply fixes from the terminal")
    p_inc.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        metavar="URL",
    )
    p_inc.add_argument(
        "--all",
        action="store_true",
        help="show all incidents including approved/dismissed",
    )
    p_inc.set_defaults(func=_cmd_incidents)

    # --- mcp ---
    p_mcp = sub.add_parser(
        "mcp",
        help="start the MCP server (VS Code, Cursor, Claude Code, Windsurf, …)",
    )
    p_mcp.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        metavar="URL",
    )
    p_mcp.add_argument(
        "--admin-token",
        default=os.getenv("ORQIS_ADMIN_TOKEN", ""),
        metavar="TOKEN",
        help="ORQIS_ADMIN_TOKEN for approve/dismiss/PR actions (or set env var)",
    )
    p_mcp.set_defaults(func=_cmd_mcp)

    # --- status ---
    p_stat = sub.add_parser("status", help="check backend health")
    p_stat.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        metavar="URL",
    )
    p_stat.set_defaults(func=_cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
