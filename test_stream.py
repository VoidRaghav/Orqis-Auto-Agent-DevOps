"""
Simulates a live server log stream for testing the Orqis daemon.
Loops continuously to mimic a real infinite server stream — this ensures
async LLM interpretations resolve while new lines are still arriving,
so they appear inline rather than batched at the end.

Usage:
  python3 test_stream.py | .venv/bin/python3 -m orqis.daemon --source test-server
  Ctrl-C to stop.
"""

import itertools
import time
from datetime import datetime, timedelta

LINES = [
    ("INFO",    "agent.executor", "AgentExecutor initialized"),
    ("INFO",    "agent.executor", "Run #{run_id} started"),
    ("INFO",    "api.client",     "Calling OpenAI API - model=gpt-4o tokens=1200"),
    ("INFO",    "api.client",     "Response received - latency=0.82s"),
    ("WARNING", "orqis.watchdog", "Cost spike - $0.41 in 0.8s"),
    ("INFO",    "agent.executor", "Tool call: search_web(query='current stock price')"),
    ("ERROR",   "agent.executor", "RecursionError: maximum recursion depth exceeded"),
    ("INFO",    "agent.executor", "Retrying run #{run_id}"),
    ("ERROR",   "api.client",     "ConnectionError: connection refused - host=api.openai.com port=443"),
    ("INFO",    "agent.executor", "Waiting for retry backoff..."),
    ("ERROR",   "api.client",     "RateLimitError: rate limit exceeded - retry after 60s"),
    ("INFO",    "agent.executor", "Run #{run_id2} started"),
    ("INFO",    "api.client",     "Calling Anthropic API - model=claude-haiku tokens=800"),
    ("ERROR",   "agent.executor", "TypeError: argument of type 'NoneType' is not iterable"),
    ("INFO",    "agent.executor", "Run #{run_id2} completed successfully"),
    ("ERROR",   "agent.executor", "Traceback (most recent call last):"),
    ("ERROR",   "agent.executor", "  File 'agent.py', line 42, in run"),
    ("ERROR",   "agent.executor", "AttributeError: 'NoneType' object has no attribute 'content'"),
    ("INFO",    "agent.executor", "Run #{run_id3} started"),
    ("INFO",    "api.client",     "Response received - latency=1.1s"),
    ("INFO",    "agent.executor", "Run #{run_id3} completed successfully"),
    ("ERROR",   "db.client",      "ConnectionError: ECONNREFUSED 127.0.0.1:5432 - PostgreSQL unreachable"),
    ("INFO",    "agent.executor", "Cycle complete - sleeping 2s before next run"),
]

import random, string

def run_id():
    return "".join(random.choices(string.hexdigits[:16], k=7))

base = datetime.now()
for cycle in itertools.count(1):
    r1, r2, r3 = run_id(), run_id(), run_id()
    for i, (level, source, msg) in enumerate(LINES):
        ts = (base + timedelta(seconds=cycle * 25 + i)).strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {level:<8} {source:<16} {msg.format(run_id=r1, run_id2=r2, run_id3=r3)}"
        print(line, flush=True)
        time.sleep(0.5)  # 500ms between lines — gives Ollama time to respond inline
