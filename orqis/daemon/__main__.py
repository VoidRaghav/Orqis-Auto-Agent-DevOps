"""
Orqis daemon entry point.

Usage:
  # Stream stdin (pipe server logs in)
  tail -f /var/log/app.log | python -m orqis.daemon

  # Tail a file directly
  python -m orqis.daemon --file /var/log/app.log

  # Specify a source label shown on the dashboard
  tail -f /var/log/app.log | python -m orqis.daemon --source my-api-server

  # Start the backend server (run this first in a separate terminal)
  python -m orqis.daemon --server
"""

import argparse
import asyncio
import sys

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="orqis",
        description="Orqis log analysis daemon",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--file",
        metavar="PATH",
        help="tail a log file instead of reading stdin",
    )
    group.add_argument(
        "--server",
        action="store_true",
        help="start the Orqis backend HTTP server",
    )
    parser.add_argument(
        "--source",
        default="unknown",
        help="label for the log source shown on the dashboard (default: unknown)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="host for the backend server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="port for the backend server (default: 8000)",
    )
    return parser.parse_args()


def run_server(host: str, port: int) -> None:
    uvicorn.run(
        "orqis.backend.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


async def run_daemon(args: argparse.Namespace) -> None:
    from ..daemon import log_reader

    if args.file:
        print(f"[orqis] tailing file: {args.file}", file=sys.stderr)
        await log_reader.tail_file(args.file, source=args.source)
    else:
        print("[orqis] reading from stdin", file=sys.stderr)
        await log_reader.read_stdin(source=args.source)


def main() -> None:
    args = parse_args()

    if args.server:
        run_server(args.host, args.port)
    else:
        try:
            asyncio.run(run_daemon(args))
        except KeyboardInterrupt:
            print("\n[orqis] daemon stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
