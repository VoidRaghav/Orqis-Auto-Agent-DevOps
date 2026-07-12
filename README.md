# Orqis AI

Autonomous self-healing ops for AI agents and DevOps pipelines.

Orqis watches logs in real time, explains what broke, and generates a patch you can review.

It works with log streams, MCP-compatible IDEs, and copy-paste prompts.

## Quick start

```bash
pip install -e .
cp .env.example .env
orqis start
orqis monitor --file /var/log/app.log --source my-app
orqis mcp
orqis status
```

## Integrate

- Stream logs from a file or process.
- Connect your app with the SDK.
- Use MCP in Cursor, Claude Code, Windsurf, VS Code, or any compatible IDE.
- Copy an incident into your assistant if you do not use MCP.

## What you get

- Real-time log monitoring
- Error classification
- Plain-English incident summaries
- Unified diff patches
- Human review before merge
