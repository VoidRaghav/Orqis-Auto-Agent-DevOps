# VibeOps

Mission Control for Vibe-Built Agents

## Overview

VibeOps is the first DevOps tool built specifically for the vibe coding era. While AI IDEs like Cursor, Windsurf, and Claude have made building AI agents trivially easy, managing what was built remains stuck in Engineer Era. VibeOps fills this critical gap by providing zero-config operational layer for non-technical builders who shipped something in Cursor and now have no idea what it's doing.

## The Problem

When an agent ships to production, builders go completely blind. They're left cobbling together:
- **LangSmith** for tracing and logs — complex setup, built for engineers
- **Supabase/Postgres** for agent memory/outputs — requires database knowledge  
- **Railway/Render** for deployment
- **Doppler/.env files** for secrets management
- **Datadog or nothing** for monitoring

None of these tools talk to each other well, and none were designed for a builder in Cursor who doesn't know what a trace is.

## The Solution

VibeOps is a zero-config operational layer that sits between the vibe coder's IDE and their running agent. It auto-instruments any agent project, captures everything the agent does, and presents it in plain English — with the ability to change how the agent behaves without touching code.

### Core Features

#### 🎯 Narrative Logs
Traditional tools produce raw JSON. VibeOps produces a story. Every agent run is displayed as a readable timeline:

```
14:02  Agent thought: "I need to find user's invoice"
14:02  Tool call: search_database → returned 0 results  
14:03  Agent re-tried: search_google → Error: API key missing
14:03  Run failed · cost: $0.004 · duration: 1.2s
```

Logs are searchable in natural language. Ask *"Why did the agent fail to book the flight yesterday?"* and get a narrative answer, not a raw event stream.

#### ⚡ Live Configuration (Hot-Swap)
- Swap AI model live — GPT-4o → Claude Sonnet without touching code
- Edit system prompt from dashboard — changes take effect on the next request  
- Inject environment variables through UI — never touch .env files again
- Run prompt A/B tests — split traffic, measure which prompt performs better

#### 🛡️ Cost Guardrail
- **Real-time burn meter** — per-agent cost in dollars as it accrues
- **Budget limits** — set max spend per agent per day or per run
- **Automatic kill switch** — budget hit → agent pauses + alert sent
- **Loop detection** — same tool called N times in a short window → auto-pause

#### 🔄 Self-Heal Loop
When an agent crashes, VibeOps captures the trace, diagnoses the root cause in plain English, packages everything the IDE agent needs, and fires it back — opening the exact file, highlighting the broken line, and injecting the fix prompt. The builder types *"fix it"* and the agent self-repairs.

**The signature feature** — one-click send-to-IDE that packages a crash and lets the agent fix itself.

#### 🧠 Context Vault (RAG Memory)
- Drag-and-drop PDFs, documents, brand guidelines — VibeOps handles chunking and embedding automatically
- Named memory slots — give the agent a "Company Context" slot that's always available
- Memory inspector — visualize what the agent "remembers" across sessions

#### 🌐 Multi-Agent Topology View
When a vibe coder builds multiple agents that talk to each other, VibeOps visualizes the full graph — which agent called which, where the bottleneck is, which agent is burning the most money.

## Getting Started

### Installation
```bash
npx install vibeops  # zero config, auto-instruments your agent project
```

### Five-Step Flow
1. **Works with any IDE** — Cursor, Windsurf, Claude, GitHub Copilot
2. **One command install** — `npx install vibeops`
3. **Auto-reads project folder** — Silently scans: .env files & secrets, agent code (.py/.ts/.js), tool & API call patterns, and prompt config files
4. **VibeOps Engine runs** — Four systems activate: narrative logs, live config, cost guardrail, and self-heal loop — all without manual setup
5. **Dashboard + self-heal feedback** — The coder gets a clean mission control dashboard. Crashes are auto-packaged and sent back to the IDE for the agent to fix itself

## The Dashboard

A mission control panel — clean, readable, and zero engineering knowledge required.

### Dashboard Tabs
- **Overview** — Agent status, runs today, cost today, average run time
- **Logs** — Full searchable narrative timeline for any agent, any time range
- **Config** — Live prompt editor, model switcher, environment variable manager
- **Cost** — Detailed cost breakdown by agent, by run, by tool call
- **Replay** — Re-run any historical agent trace with one click for debugging

## Technical Architecture

VibeOps is a lightweight proxy layer. It does not replace the agent's infrastructure — it wraps it.

### Core Components
- **Instrumentation shim** — Injects into the project via `npx install vibeops`
- **Event streaming** — Real-time WebSocket to VibeOps cloud
- **Dashboard** — Subscribes to the event stream and renders live
- **Self-heal loop** — Listens for error events and triggers IDE integration via MCP

### MCP Integration
VibeOps is built as an MCP (Model Context Protocol) server, allowing any AI IDE that supports MCP to natively communicate with it:

```json
{
  "servers": {
    "vibeops": {
      "url": "https://mcp.vibeops.io/sse",
      "name": "VibeOps"
    }
  }
}
```

### SDK Support
The shim supports all major agent frameworks out of the box — zero manual config:
- OpenAI SDK
- Anthropic SDK  
- LangChain
- LlamaIndex
- Custom agents

## Pricing

The Spotify Premium model: people pay for convenience even when free alternatives exist. Setting up LangSmith, writing SDK instrumentation, and self-hosting a logging stack is high-friction. VibeOps being plug-and-play is the value proposition.

### Plans
- **Free** — $0/month
  - 1 agent
  - Basic narrative logs
  - 3-day log retention
  - Community support

- **Pro** — $20/month
  - Unlimited agents
  - Cost tracking & kill switch
  - Send to IDE (self-heal)
  - Live config hot-swap
  - 30-day retention
  - Slack/email alerts

- **Team** — $79/month
  - Everything in Pro
  - Multi-agent topology view
  - Shared prompt versioning
  - Prompt A/B testing
  - Context vault (RAG memory)
  - Priority support

## Competitive Landscape

| Feature | LangSmith | Supabase | InsForge | **VibeOps** |
|----------|------------|------------|------------|----------------|
| Primary user | Engineers | Full-stack devs | Vibe coders | **Vibe coders** |
| Setup complexity | High — manual SDK | Medium — DB knowledge | Low — CLI | **Zero — npx one-liner** |
| Log style | Technical JSON | Database rows | Structured logs | **Narrative / intent-based** |
| Configuration | Code + redeploy | Code + redeploy | Dashboard (limited) | **Live hot-swap** |
| Error recovery | Human reads logs | Human reads logs | Human reads logs | **Agent self-heals via IDE** |
| Cost tracking | No | No | Partial | **Real-time + kill switch** |

## Roadmap

### Phase 1 · Months 1–3 (MVP)
- One-line SDK for OpenAI + Anthropic
- Narrative log viewer
- Basic error alerting
- Target: 10 vibe coders this week

### Phase 2 · Months 3–6 (Core Product)
- Live config (model swap, prompt editor)
- Cost tracking + kill switch
- Send to IDE via MCP
- Loop detection + auto-pause

### Phase 3 · Months 6–12 (Moat)
- Context vault (RAG memory)
- Multi-agent topology view
- Prompt A/B testing
- Replay + time-machine debug

## Why Now

2026 is the year of agentic churn. People are realizing building an agent is easy; running it is hard. The window before LangSmith/Datadog reach vibe-coder parity is approximately 12–18 months. Speed of execution is everything.

## The One-Line Summary

**InsForge built the city. VibeOps builds the air traffic control.**

---

*VibeOps · April 2026 · v1.0 · Confidential*

<p align="center">
  <i>Build fast. Understand faster. Fixes things instantly.</i>
</p>

---

<!-- GRADIENT LINE -->
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,100:1e293b&height=100&section=header"/>
</p>

---

## 🧠 What is VibeOps?

<div align="center">

**VibeOps is a zero-config DevOps layer for AI agents.**  
It turns your agents from black boxes into **observable, controllable, self-healing systems**.

</div>

---

## ⚡ The Problem

<table align="center">
<tr>
<td align="center">❌ No visibility</td>
<td align="center">❌ Debugging = guessing</td>
<td align="center">❌ Costs out of control</td>
<td align="center">❌ Redeploy hell</td>
</tr>
</table>

---

## 💡 The Solution

<div align="center">

| Feature | What You Get |
|--------|-------------|
| 📖 Narrative Logs | Understand agent thinking |
| 🔄 Live Config | Change behavior instantly |
| 💸 Cost Guardrail | Control spending in real-time |
| 🧠 Self-Heal Loop | Fix errors directly from IDE |

</div>

---

## 🚀 Quick Start

```bash
npx install vibeops
````

<p align="center">
⚡ No config • No setup • No friction
</p>

---

## 🔥 Core Features

### 📖 Narrative Logs

```text
14:02  Agent thought: "Find invoice"
14:03  Tool call failed: API key missing
14:03  Run failed · cost: $0.004
```

---

### 🔄 Live Config

* Switch models instantly
* Edit prompts in real-time
* Inject environment variables

---

### 💸 Cost Guardrails

* Real-time spend tracking
* Budget limits
* Auto kill-switch

---

### 🧠 Self-Healing Loop

<div align="center">

```text
Crash → Diagnose → Send to IDE → Fix → Re-run → ✅
```

</div>

---

## 🧩 Tech Stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=nodejs,ts,react,vercel" />
</p>

<div align="center">

OpenAI • Anthropic • LangChain • MCP • WebSockets

</div>

---

## 🗺️ Roadmap

```diff
+ Narrative Logs
+ Zero-config install
- Live dashboard
- Cost tracking
- Self-healing loop
- Multi-agent view
```

---

## 🧠 Vision

<div align="center">

We are moving from

### ⚙️ Code-First → 🤖 Agent-First

But infrastructure is still stuck in the past.

</div>

---

## 🏁 TL;DR

<div align="center">

> InsForge built the city.
> **VibeOps builds the air traffic control.**

</div>

---

<!-- FOOTER WAVE -->

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:1e293b,100:0f172a&height=120&section=footer"/>
</p>
