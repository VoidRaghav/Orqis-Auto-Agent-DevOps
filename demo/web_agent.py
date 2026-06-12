#!/usr/bin/env python3
"""
Orqis demo — RefundBot web UI.

A browser-visible version of demo/support_agent.py so the runaway loop can be
shown live on a screen, not just in a terminal. Serves one page on :8200:

  - a customer asks for a refund
  - the agent's tool calls stream in real time, the cost ticker climbs
  - Orqis (watching the same stream on :8000) trips the circuit breaker
  - the page shows the agent halted, money saved, with a link to the dashboard

Run all three for a demo:
  1. orqis start                      # backend + detection on :8000
  2. cd frontend && npm run dev       # Orqis dashboard on :3000
  3. python demo/web_agent.py         # this agent UI on :8200

Then open http://localhost:8200 and http://localhost:3000/dashboard side by side.
"""

import asyncio
import importlib
import json
import os
import re

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

import support_agent as agent

PORT = int(os.getenv("ORQIS_AGENT_PORT", "8200"))
DASHBOARD_URL = os.getenv("ORQIS_DASHBOARD_URL", "http://localhost:3000/dashboard")
BACKEND_URL = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")
# Orqis broadcasts incident.approved over this WebSocket; the page listens so it
# can auto-run the fixed agent the moment the patch is applied in the dashboard.
WS_URL = BACKEND_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
AGENT_FILE = agent.__file__

# The canonical broken business logic. /break rewrites resolve_refund back to
# this so the full break -> fix -> verify cycle can be demoed repeatedly.
_BROKEN_FN = '''def resolve_refund(order_id: str) -> str:
    """Answer the customer's refund question by checking the order status."""
    status = check_order_status(order_id)
    while status == "processing":
        status = check_order_status(order_id)
    return f"Your refund for order {order_id} is {status}."'''

# Matches the resolve_refund definition (broken OR Orqis-patched) up to the
# marker comment that follows it, so we can swap the body in place.
_FN_RE = re.compile(
    r"def resolve_refund\(order_id: str\) -> str:.*?(?=\n+# Line that falls inside)",
    re.DOTALL,
)

# Only one session runs at a time — the demo is sequential, and reloading the
# module mid-run would be unsafe.
_run_lock = asyncio.Lock()

app = FastAPI(title="RefundBot demo")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _PAGE.replace("__DASHBOARD__", DASHBOARD_URL).replace("__WSURL__", WS_URL)


@app.get("/run")
async def run() -> StreamingResponse:
    """Run one refund session, streaming each step to the browser over SSE."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict) -> None:
        # run_session executes in a worker thread — hop back to the loop safely.
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def stream():
        async with _run_lock:
            # Reload from disk so a just-approved Orqis patch takes effect. The
            # running server imported the agent once; without this it would keep
            # executing the old in-memory code after the file was patched.
            importlib.reload(agent)
            future = loop.run_in_executor(None, lambda: agent.run_session(emit))
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    if future.done() and queue.empty():
                        break
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/clear")
async def clear() -> dict:
    """
    Wipe the dashboard (incidents, log stream, traces/cost) for a fresh run.
    Proxied through this server so the same-origin page avoids a cross-origin
    call to the backend.
    """
    import urllib.request
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"{BACKEND_URL}/demo/reset?clear=true", data=b"", method="POST"),
            timeout=5,
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/break")
async def rebreak() -> dict:
    """
    Restore the original unbounded loop so the demo can be run again. Reverts
    whatever Orqis patched and clears the dashboard's incident list.
    """
    try:
        with open(AGENT_FILE, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        return {"ok": False, "error": str(e)}

    new_source, n = _FN_RE.subn(_BROKEN_FN, source)
    if n:
        with open(AGENT_FILE, "w", encoding="utf-8") as f:
            f.write(new_source)

    # Clear stored incidents so the dashboard starts fresh for the next run.
    backend = os.getenv("ORQIS_BACKEND_URL", "http://localhost:8000")
    try:
        import urllib.request
        urllib.request.urlopen(
            urllib.request.Request(f"{backend}/demo/reset?clear=true", data=b"", method="POST"),
            timeout=5,
        )
    except Exception:
        pass

    return {"ok": True, "reverted": bool(n)}


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>RefundBot — AI support agent</title>
<style>
  :root { --bg:#0a0a0f; --panel:#13131c; --line:#23232f; --dim:#8a8aa0;
          --purple:#8b5cf6; --pink:#ec4899; --red:#ef4444; --green:#22c55e; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:#e8e8f0;
         font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }
  .wrap { max-width:760px; margin:0 auto; padding:32px 20px 64px; }
  .top { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
  .brand { font-weight:700; font-size:18px; letter-spacing:.5px; }
  .brand span { background:linear-gradient(90deg,var(--purple),var(--pink));
                -webkit-background-clip:text; background-clip:text; color:transparent; }
  .pill { font-size:12px; padding:4px 10px; border-radius:999px; border:1px solid var(--line);
          color:var(--dim); }
  .pill.live { color:var(--green); border-color:#1c3a26; background:#0c1a11; }
  .pill.burning { color:var(--red); border-color:#3a1c1c; background:#1a0c0c; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:14px;
          padding:20px; margin-bottom:18px; }
  .customer { display:flex; gap:12px; align-items:flex-start; }
  .avatar { width:34px; height:34px; border-radius:10px; flex:none;
            background:linear-gradient(135deg,#2a2a3a,#1a1a26);
            display:flex; align-items:center; justify-content:center; font-size:16px; }
  .bubble { background:#1c1c28; border:1px solid var(--line); border-radius:12px;
            padding:10px 14px; }
  .meta { color:var(--dim); font-size:12px; margin-bottom:4px; }
  .stats { display:flex; gap:14px; margin:18px 0; }
  .stat { flex:1; background:var(--panel); border:1px solid var(--line);
          border-radius:12px; padding:14px 16px; }
  .stat .k { color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.6px; }
  .stat .v { font-size:26px; font-weight:700; margin-top:4px; }
  .stat.cost .v { color:var(--red); }
  .console { background:#08080c; border:1px solid var(--line); border-radius:12px;
             padding:14px 16px; min-height:140px; max-height:300px; overflow:auto; font-size:13px; }
  .row { padding:3px 0; color:#c7c7d8; }
  .row .n { color:var(--purple); }
  .row .cost { color:var(--red); }
  .banner { border-radius:12px; padding:16px 18px; margin-top:18px; display:none; }
  .banner.show { display:block; }
  .banner.halted { background:#0c1a11; border:1px solid #1c3a26; color:#bdf0cd; }
  .banner.halted b { color:var(--green); }
  .banner.fixed { background:#0c1320; border:1px solid #1c2c4a; color:#bcd4f5; }
  .banner.fixed b { color:#7fb2ff; }
  .banner.backstop { background:#1a160c; border:1px solid #3a311c; color:#f0e6bd; }
  .actions { display:flex; gap:12px; margin-top:22px; align-items:center; }
  button { font:inherit; font-weight:600; cursor:pointer; border:none; border-radius:10px;
           padding:11px 20px; color:#fff;
           background:linear-gradient(90deg,var(--purple),var(--pink)); }
  button:disabled { opacity:.5; cursor:default; }
  a.dash { color:var(--dim); text-decoration:none; border-bottom:1px dashed var(--line); }
  a.dash:hover { color:#fff; }
  .hint { color:var(--dim); font-size:12px; margin-top:10px; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand"><span>RefundBot</span> · AI customer support</div>
      <div id="status" class="pill">idle</div>
    </div>

    <div class="card">
      <div class="customer">
        <div class="avatar">🙋</div>
        <div>
          <div class="meta">customer · order #1042</div>
          <div class="bubble" id="customerMsg">Click “Send refund request” to start.</div>
        </div>
      </div>
    </div>

    <div class="stats">
      <div class="stat cost"><div class="k">Money burned</div><div class="v" id="spent">$0.00</div></div>
      <div class="stat"><div class="k">Tool calls</div><div class="v" id="calls">0</div></div>
      <div class="stat"><div class="k">Customers helped</div><div class="v" id="helped">0</div></div>
    </div>

    <div class="console" id="console"><div class="row" style="color:#5a5a6a">agent idle…</div></div>

    <div class="banner halted" id="halted"></div>
    <div class="banner fixed" id="fixed"></div>
    <div class="banner backstop" id="backstop"></div>

    <div class="actions">
      <button id="runBtn" onclick="run()">Send refund request</button>
      <button id="breakBtn" onclick="rebreak()" style="background:#23232f">Reset &amp; re-break agent</button>
      <a class="dash" href="__DASHBOARD__" target="_blank">Open Orqis dashboard →</a>
    </div>
    <div class="hint">The agent has no exit condition for an ambiguous order status. Watch the
      cost climb — then watch Orqis stop it from the live trace stream. After you Apply the fix
      in the dashboard, click “Send refund request” again to see the agent run correctly.</div>
  </div>

<script>
const $ = id => document.getElementById(id);
let es = null;
let running = false;

// Listen to Orqis's live WebSocket. The instant a fix is applied in the
// dashboard, Orqis broadcasts incident.approved for this agent — we re-run
// automatically so the fixed agent's logs stream without a manual click.
function watchOrqis() {
  let ws;
  try { ws = new WebSocket("__WSURL__"); } catch (e) { return; }
  ws.onmessage = (e) => {
    let msg; try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.type === "incident.approved" && msg.data && msg.data.source === "support-agent" && !running) {
      setStatus("fix applied — re-running…", "live");
      setTimeout(() => run(false), 600);  // append the fixed run; don't wipe the broken one
    }
  };
  ws.onclose = () => setTimeout(watchOrqis, 2500);
  ws.onerror = () => ws.close();
}
watchOrqis();

function setStatus(text, cls) { const s=$("status"); s.textContent=text; s.className="pill "+(cls||""); }
function addRow(html) {
  const c=$("console"); if (c.dataset.fresh!=="1"){ c.innerHTML=""; c.dataset.fresh="1"; }
  const d=document.createElement("div"); d.className="row"; d.innerHTML=html;
  c.appendChild(d); c.scrollTop=c.scrollHeight;
}

function run(manual=true) {
  if (running) return;
  running = true;
  $("runBtn").disabled=true; $("breakBtn").disabled=true;
  $("halted").className="banner halted"; $("backstop").className="banner backstop";
  $("fixed").className="banner fixed";
  $("console").innerHTML=""; $("console").dataset.fresh="1";
  $("spent").textContent="$0.00"; $("calls").textContent="0"; $("helped").textContent="0";
  setStatus(manual ? "running" : "fix applied — running","burning");

  // A manual run starts a fresh cycle, so wipe the dashboard first. The auto
  // re-run after a fix appends instead, so the broken + fixed runs tell the
  // full story side by side.
  const start = () => { es = new EventSource("/run"); bind(); };
  if (manual) { fetch("/clear", { method: "POST" }).finally(start); }
  else { start(); }
}

function bind() {
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type==="customer") { $("customerMsg").textContent=ev.text; }
    else if (ev.type==="call") {
      $("spent").textContent="$"+ev.spent.toFixed(2);
      $("calls").textContent=ev.n;
      addRow(`<span class="n">call #${ev.n}</span> &nbsp;${ev.tool}("${ev.args}") → '${ev.result}' &nbsp; <span class="cost">+$${ev.cost.toFixed(2)}</span> &nbsp; <span style="color:#6a6a7a">($${ev.spent.toFixed(2)} burned)</span>`);
    }
    else if (ev.type==="warn") { addRow(`<span style="color:#f0c674">${ev.text}</span>`); }
    else if (ev.type==="halted") {
      setStatus("halted by Orqis","live");
      const b=$("halted"); b.className="banner halted show";
      b.innerHTML=`<b>✓ Orqis tripped the circuit breaker — agent halted.</b><br>
        Stopped after <b>${ev.calls} calls</b> / <b>$${ev.spent.toFixed(2)}</b>.
        Left running, this loop would have burned $4+ and frozen the support queue.
        Orqis has filed an incident with a verified one-click fix.`;
    }
    else if (ev.type==="backstop") {
      setStatus("backstop","");
      const b=$("backstop"); b.className="banner backstop show";
      b.innerHTML=`Backstop hit at ${ev.calls} calls ($${ev.spent.toFixed(2)}). Is the Orqis backend running on :8000?`;
    }
    else if (ev.type==="resolved") {
      setStatus("fixed — running correctly","live"); $("helped").textContent="1";
      addRow(`<span style="color:#7fb2ff">agent → ${ev.text}</span>`);
      const b=$("fixed"); b.className="banner fixed show";
      b.innerHTML=`<b>✓ Orqis's fix is live — the agent now runs correctly.</b><br>
        It bounded its retries and escalated to a human after ${ev.calls} calls
        ($${ev.spent.toFixed(2)}) instead of looping forever. No runaway, nothing for
        Orqis to flag.`;
    }
    else if (ev.type==="end") { es.close(); running=false; $("runBtn").disabled=false; $("breakBtn").disabled=false; }
  };
  es.onerror = () => { es.close(); running=false; $("runBtn").disabled=false; $("breakBtn").disabled=false; setStatus("disconnected",""); };
}

async function rebreak() {
  $("runBtn").disabled=true; $("breakBtn").disabled=true;
  setStatus("re-breaking…","");
  try { await fetch("/break", { method:"POST" }); } catch (e) {}
  $("halted").className="banner halted"; $("fixed").className="banner fixed";
  $("backstop").className="banner backstop";
  $("console").innerHTML='<div class="row" style="color:#5a5a6a">agent idle…</div>';
  $("console").dataset.fresh="0";
  $("spent").textContent="$0.00"; $("calls").textContent="0"; $("helped").textContent="0";
  $("customerMsg").textContent='Click "Send refund request" to start.';
  setStatus("idle — agent re-broken","");
  $("runBtn").disabled=false; $("breakBtn").disabled=false;
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print(f"[orqis] RefundBot demo UI on http://localhost:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
