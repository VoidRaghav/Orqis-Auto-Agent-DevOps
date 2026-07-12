#!/usr/bin/env bash
# Orqis dogfood harness — preflight + Tier A (+ Tier B if CURSOR_API_KEY set).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> preflight"
python scripts/preflight.py

echo "==> Tier A: pipeline runaway"
pytest tests/test_pipeline_runaway.py -v

if [[ -n "${CURSOR_API_KEY:-}" ]]; then
  echo "==> Tier B: agent IDE flow"
  pytest tests/test_agent_ide_flow.py -v
else
  echo "SKIP Tier B: CURSOR_API_KEY not set"
fi
