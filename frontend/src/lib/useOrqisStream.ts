"use client";

import { useEffect, useRef, useReducer, useCallback } from "react";
import type { LogEvent, TraceEvent, Incident, WsPayload, ChangeLogEntry, GithubConnectInfo, AgentStatus } from "./types";
import { MULTI_TENANT } from "./env";

const MAX_EVENTS = 500;
export const ADMIN_TOKEN_KEY = "orqis_admin_token";

export function adminHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  return token ? { "X-Orqis-Admin-Token": token } : {};
}

function apiInit(): RequestInit {
  return {
    credentials: MULTI_TENANT ? "include" : "same-origin",
    headers: { ...adminHeaders() },
  };
}

interface State {
  events: LogEvent[];
  traces: TraceEvent[];
  incidents: Incident[];
  changes: ChangeLogEntry[];
  agents: Record<string, AgentStatus>;
  github: GithubConnectInfo | null;
  connected: boolean;
}

type Action =
  | { type: "connected" }
  | { type: "disconnected" }
  | { type: "log_event"; event: LogEvent }
  | { type: "log_interp"; event_id: string; text: string }
  | { type: "trace_event"; event: TraceEvent }
  | { type: "trace_interp"; event_id: string; text: string }
  | { type: "incident_upsert"; incident: Incident }
  | { type: "change_logged"; entry: ChangeLogEntry }
  | { type: "changes_loaded"; changes: ChangeLogEntry[] }
  | { type: "agent_status"; agent: AgentStatus }
  | { type: "agents_loaded"; agents: AgentStatus[] }
  | { type: "github_loaded"; github: GithubConnectInfo }
  | { type: "store_cleared" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "connected":    return { ...state, connected: true };
    case "disconnected": return { ...state, connected: false };

    case "log_event": {
      const events = [action.event, ...state.events].slice(0, MAX_EVENTS);
      return { ...state, events };
    }
    case "log_interp": {
      const events = state.events.map(e =>
        e.id === action.event_id ? { ...e, interpretation: action.text } : e
      );
      return { ...state, events };
    }
    case "trace_event": {
      const traces = [action.event, ...state.traces].slice(0, MAX_EVENTS);
      return { ...state, traces };
    }
    case "trace_interp": {
      const traces = state.traces.map(t =>
        t.id === action.event_id ? { ...t, interpretation: action.text } : t
      );
      return { ...state, traces };
    }
    case "incident_upsert": {
      const idx = state.incidents.findIndex(i => i.id === action.incident.id);
      const incidents = idx >= 0
        ? state.incidents.map((i, n) => n === idx ? action.incident : i)
        : [action.incident, ...state.incidents];
      return { ...state, incidents };
    }
    case "change_logged": {
      if (state.changes.some(c => c.id === action.entry.id)) return state;
      const changes = [action.entry, ...state.changes].slice(0, MAX_EVENTS);
      return { ...state, changes };
    }
    case "changes_loaded":
      return { ...state, changes: action.changes };
    case "agent_status":
      return { ...state, agents: { ...state.agents, [action.agent.source]: action.agent } };
    case "agents_loaded":
      return {
        ...state,
        agents: Object.fromEntries(action.agents.map((a) => [a.source, a])),
      };
    case "github_loaded":
      return { ...state, github: action.github };
    case "store_cleared":
      return { ...state, incidents: [], events: [], traces: [], changes: [] };
  }
}

export function useOrqisStream(wsUrl: string, apiUrl: string) {
  const [state, dispatch] = useReducer(reducer, {
    events: [], traces: [], incidents: [], changes: [], agents: {}, github: null, connected: false,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshGithub = useCallback(async () => {
    try {
      const r = await fetch(`${apiUrl}/integrations/github/connect`, apiInit());
      if (!r.ok) return;
      const github: GithubConnectInfo = await r.json();
      dispatch({ type: "github_loaded", github });
    } catch {
      // ignore — badge stays on last known state
    }
  }, [apiUrl]);

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    let url = wsUrl;
    if (MULTI_TENANT) {
      try {
        const r = await fetch(`${apiUrl}/auth/ws-ticket`, apiInit());
        if (r.ok) {
          const { ticket } = await r.json();
          const sep = wsUrl.includes("?") ? "&" : "?";
          url = `${wsUrl}${sep}ticket=${encodeURIComponent(ticket)}`;
        }
      } catch {
        // fall through — server will reject if auth required
      }
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => dispatch({ type: "connected" });
    ws.onclose = () => {
      dispatch({ type: "disconnected" });
      retryRef.current = setTimeout(connect, 2500);
    };
    ws.onerror = () => ws.close();

    ws.onmessage = (ev) => {
      try {
        const payload: WsPayload = JSON.parse(ev.data);
        switch (payload.type) {
          case "log.event":
            dispatch({ type: "log_event", event: payload.data });
            break;
          case "log.interpretation":
            dispatch({ type: "log_interp", event_id: payload.data.event_id, text: payload.data.interpretation });
            break;
          case "trace.event":
            dispatch({ type: "trace_event", event: payload.data });
            break;
          case "trace.interpretation":
            dispatch({ type: "trace_interp", event_id: payload.data.event_id, text: payload.data.interpretation });
            break;
          case "incident.created":
          case "incident.located":
          case "incident.patched":
          case "incident.updated":
          case "incident.approved":
          case "incident.dismissed":
          case "incident.pr_opened":
          case "incident.resolved":
          case "incident.interpretation":
            dispatch({ type: "incident_upsert", incident: payload.data });
            break;
          case "change.logged":
            dispatch({ type: "change_logged", entry: payload.data });
            break;
          case "agent.status":
            dispatch({ type: "agent_status", agent: payload.data });
            break;
          case "settings.updated":
            dispatch({ type: "github_loaded", github: payload.data });
            break;
          case "store.cleared":
            dispatch({ type: "store_cleared" });
            break;
        }
      } catch {}
    };
  }, [wsUrl, apiUrl]);

  useEffect(() => {
    const init = apiInit();
    fetch(`${apiUrl}/incidents?limit=50`, init)
      .then(r => r.json())
      .then((list: Incident[]) => {
        list.forEach(incident => dispatch({ type: "incident_upsert", incident }));
      })
      .catch(() => {});

    fetch(`${apiUrl}/changes?limit=100`, init)
      .then(r => r.json())
      .then((list: ChangeLogEntry[]) => {
        dispatch({ type: "changes_loaded", changes: [...list].reverse() });
      })
      .catch(() => {});

    fetch(`${apiUrl}/agents`, init)
      .then(r => r.json())
      .then((list: AgentStatus[]) => {
        if (Array.isArray(list)) dispatch({ type: "agents_loaded", agents: list });
      })
      .catch(() => {});

    refreshGithub();
  }, [apiUrl, refreshGithub]);

  // Refresh GitHub badge when the user returns to the tab
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshGithub();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshGithub]);

  useEffect(() => {
    connect();
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const postInit = (): RequestInit => ({
    method: "POST",
    credentials: MULTI_TENANT ? "include" : "same-origin",
    headers: adminHeaders(),
  });

  const approveIncident = useCallback(async (id: string, force = false) => {
    const url = `${apiUrl}/incidents/${id}/approve${force ? "?force=true" : ""}`;
    const r = await fetch(url, postInit());
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  const dismissIncident = useCallback(async (id: string) => {
    const r = await fetch(`${apiUrl}/incidents/${id}/dismiss`, postInit());
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  const openPr = useCallback(async (id: string) => {
    const r = await fetch(`${apiUrl}/incidents/${id}/open-pr`, postInit());
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  const resolveIncident = useCallback(async (id: string) => {
    const r = await fetch(`${apiUrl}/incidents/${id}/resolve`, postInit());
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  const copyPrompt = useCallback(async (id: string): Promise<string> => {
    const r = await fetch(`${apiUrl}/incidents/${id}/prompt`, apiInit());
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    return data.prompt as string;
  }, [apiUrl]);

  return {
    ...state,
    approveIncident,
    dismissIncident,
    openPr,
    resolveIncident,
    copyPrompt,
    refreshGithub,
  };
}
