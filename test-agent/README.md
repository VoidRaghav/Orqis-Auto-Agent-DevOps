# orqis-test-agent

A minimal **user project** for Orqis dogfood testing. This repo simulates what a real customer would have: buggy agent code, a small `src/` tree, and Orqis MCP config in the project root.

The Orqis harness lives in the main [Orqis-Auto-Agent-DevOps](https://github.com/Siddarthb07/Orqis-Auto-Agent-DevOps) repo. This repo is only the target project that Orqis watches and patches.

## Setup

1. Clone this repo (or use this folder as a standalone checkout):

   ```bash
   git clone https://github.com/Siddarthb07/orqis-test-agent.git
   cd orqis-test-agent
   ```

2. Point Orqis at this project:

   ```bash
   export ORQIS_PROJECT_ROOT=/path/to/orqis-test-agent
   ```

   On Windows PowerShell:

   ```powershell
   $env:ORQIS_PROJECT_ROOT = "C:\path\to\orqis-test-agent"
   ```

3. Start the Orqis backend (from the Orqis repo) on `http://localhost:8000`, then open this folder in Cursor. The `.mcp.json` here wires the Orqis MCP server to that backend.

4. Set `ORQIS_ADMIN_TOKEN` in your environment (and in `.mcp.json` `env` if using Cursor MCP) before approving incidents.

## Layout

```
fixtures/
  refund_agent.buggy.py   # unbounded while loop in resolve_refund
  payment.buggy.py        # NameError — fee is undefined
src/
  refund_agent.py         # active copy (reset from fixtures by harness)
  payment.py
  shop_api.py             # imports payment; crashes on run
```

## Known bugs (intentional)

| File | Bug | How to trigger |
|------|-----|----------------|
| `src/refund_agent.py` | `resolve_refund` spins forever while status stays `"processing"` | `python -c "from refund_agent import resolve_refund; resolve_refund('1042')"` (from `src/`) |
| `src/payment.py` | `calculate_total` references undefined `fee` | `python shop_api.py` (from `src/`) |

The Orqis harness resets `src/` from `fixtures/` before each test run. Do not add test harness code here — keep this repo limited to what an end user would commit.

## MCP config

`.mcp.json` connects Cursor to Orqis via stdio:

- Command: `orqis mcp --backend-url http://localhost:8000`
- Requires `orqis` CLI installed (`pip install -e .` from the Orqis repo)
- Set `ORQIS_ADMIN_TOKEN` for write tools (`approve_incident`, etc.)
