"""
Realistic log stream for testing Orqis end-to-end.

Simulates a Python web backend + LLM agent — the kind of thing you'd deploy
on Railway or Vercel. Prints logs to stdout so you can pipe into orqis monitor:

    python test_stream.py | .venv/bin/orqis monitor --source test-app
    python test_stream.py --loop | .venv/bin/orqis monitor --source test-app

Or run the one-shot form to verify RCA fires without waiting forever.
"""

import argparse
import time

LOGS = [
    # Startup
    "2024-01-15 10:00:00 INFO  [server] Starting API server on port 8080",
    "2024-01-15 10:00:01 INFO  [db] Connected to PostgreSQL at db.internal:5432",
    "2024-01-15 10:00:01 INFO  [redis] Redis connection pool ready (max=20)",
    "2024-01-15 10:00:02 INFO  [server] Ready to serve requests",

    # Normal traffic
    "2024-01-15 10:00:05 INFO  [api] POST /api/chat 200 OK 312ms",
    "2024-01-15 10:00:06 INFO  [api] GET /api/history 200 OK 45ms",
    "2024-01-15 10:00:07 INFO  [llm] openai.chat run_id=abc123 model=gpt-4o tokens=1250 cost=$0.0038",

    # Connection error
    "2024-01-15 10:00:10 ERROR [db] ConnectionError: could not connect to server: Connection refused (host=db.internal port=5432)",

    # HTTP 500
    "2024-01-15 10:00:12 ERROR [api] POST /api/chat 500 Internal Server Error 2104ms",

    # Python traceback — will trigger RCA pipeline
    'Traceback (most recent call last):',
    '  File "/app/api/chat.py", line 84, in handle_chat',
    '    response = await llm_client.complete(messages, timeout=30)',
    '  File "/app/llm/client.py", line 42, in complete',
    '    result = await self._pool.execute(payload)',
    '  File "/app/llm/pool.py", line 117, in execute',
    '    conn = self._connections[self._round_robin_index % len(self._connections)]',
    'ZeroDivisionError: integer division or modulo by zero',

    # Recovery
    "2024-01-15 10:00:13 WARNING [db] Reconnecting to database (attempt 1/5)",
    "2024-01-15 10:00:14 INFO  [db] Database reconnected successfully",

    # Rate limit
    "2024-01-15 10:00:20 ERROR [llm] RateLimitError: Rate limit exceeded for model gpt-4o. Retry after 60s. (openai)",
    "2024-01-15 10:00:21 WARNING [llm] Falling back to gpt-3.5-turbo for this request",

    # Auth error
    "2024-01-15 10:00:30 ERROR [auth] AuthenticationError: JWT signature verification failed for user_id=usr_9x2kp",

    # Second traceback — different file
    'Traceback (most recent call last):',
    '  File "/app/workers/billing.py", line 23, in process_invoice',
    '    total = sum(item["amount"] for item in invoice["line_items"])',
    '  File "/app/workers/billing.py", line 23, in <genexpr>',
    '    total = sum(item["amount"] for item in invoice["line_items"])',
    'KeyError: "amount"',

    # Timeout
    "2024-01-15 10:00:35 ERROR [api] TimeoutError: upstream LLM call timed out after 30s (run_id=xyz789)",

    # Memory
    "2024-01-15 10:00:40 CRITICAL [worker] MemoryError: unable to allocate 2.1GiB for embedding batch",

    # Back to normal
    "2024-01-15 10:00:45 INFO  [api] POST /api/embed 200 OK 234ms",
    "2024-01-15 10:00:46 INFO  [api] GET /api/chat 200 OK 56ms",
    "2024-01-15 10:00:50 INFO  [scheduler] Processed 142 queued jobs in 2.1s",

    # AttributeError traceback
    'Traceback (most recent call last):',
    '  File "/app/api/embeddings.py", line 51, in embed_document',
    '    tokens = tokenizer.encode(document.content)',
    'AttributeError: "NoneType" object has no attribute "content"',

    # Import error
    "2024-01-15 10:01:00 ERROR [plugin] ImportError: cannot import name 'AsyncOpenAI' from 'openai' (version 0.28 installed, need 1.0+)",

    # Normal end
    "2024-01-15 10:01:05 INFO  [api] POST /api/chat 200 OK 445ms",
    "2024-01-15 10:01:06 INFO  [api] GET /api/history 200 OK 38ms",
    "2024-01-15 10:01:10 INFO  [server] Uptime: 70s, requests: 18, errors: 7",
]

# Errors get a small pause so the terminal is readable; tracebacks come fast
DELAYS = []
for line in LOGS:
    if line.startswith("Traceback") or line.startswith("  File"):
        DELAYS.append(0.15)
    elif "ERROR" in line or "CRITICAL" in line:
        DELAYS.append(0.5)
    else:
        DELAYS.append(0.3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="loop forever (keeps stream open for async LLM responses)")
    args = parser.parse_args()

    try:
        while True:
            for log, delay in zip(LOGS, DELAYS):
                print(log, flush=True)
                time.sleep(delay)
            if not args.loop:
                # One-shot: pause so async tasks finish before process exits
                time.sleep(3)
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
