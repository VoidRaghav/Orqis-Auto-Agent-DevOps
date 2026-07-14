# Orqis Agent SDK

One line to stream your AI agent's traces to [Orqis](https://orqis-auto-agent-dev-ops.vercel.app) —
autonomous self-healing ops for AI agents.

## Install

```bash
pip install orqis-agent-sdk
```

## Use

```python
import orqis

orqis.init(api_key="orqs_your_workspace_key")
```

That's it. Every OpenAI, Anthropic, and LangChain call in your process is captured and
streamed to your Orqis workspace, where incidents are detected and fix PRs are proposed
automatically. Nothing else in your code changes.

Get your API key from your workspace **Settings -> API keys**.

## Configuration

| Argument / env var                    | Default      | Purpose                             |
| ------------------------------------- | ------------ | ----------------------------------- |
| `api_key` / `ORQIS_API_KEY`           | -            | Routes traces to your workspace     |
| `backend_url` / `ORQIS_BACKEND_URL`   | hosted Orqis | Point at a self-hosted backend      |

The SDK never blocks or crashes your agent: events are queued on a background daemon
thread and dropped silently if the backend is unreachable. All detection, root-cause
analysis, and patch generation happen server-side — none of that logic ships in this
package.

## License

MIT
