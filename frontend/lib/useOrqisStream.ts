"use client";

import { useEffect, useRef, useReducer, useCallback } from "react";
import type { LogEvent, TraceEvent, Incident, WsPayload } from "./types";

const MAX_EVENTS = 500;

interface State {
  events: LogEvent[];
  traces: TraceEvent[];
  incidents: Incident[];
  connected: boolean;
}

type Action =
  | { type: "connected" }
  | { type: "disconnected" }
  | { type: "log_event"; event: LogEvent }
  | { type: "log_interp"; event_id: string; text: string }
  | { type: "trace_event"; event: TraceEvent }
  | { type: "trace_interp"; event_id: string; text: string }
  | { type: "incident_upsert"; incident: Incident };

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
  }
}

export function useOrqisStream(wsUrl: string, apiUrl: string) {
  const [state, dispatch] = useReducer(reducer, {
    events: [], traces: [], incidents: [], connected: false,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl);
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
          case "incident.interpretation":
            dispatch({ type: "incident_upsert", incident: payload.data });
            break;
        }
      } catch {}
    };
  }, [wsUrl]);

  // Fetch recent incidents on mount via REST
  useEffect(() => {
    fetch(`${apiUrl}/incidents?limit=50`)
      .then(r => r.json())
      .then((list: Incident[]) => {
        list.forEach(incident => dispatch({ type: "incident_upsert", incident }));
      })
      .catch(() => {});
  }, [apiUrl]);

  useEffect(() => {
    connect();
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const approveIncident = useCallback(async (id: string) => {
    const r = await fetch(`${apiUrl}/incidents/${id}/approve`, { method: "POST" });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  const dismissIncident = useCallback(async (id: string) => {
    const r = await fetch(`${apiUrl}/incidents/${id}/dismiss`, { method: "POST" });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }, [apiUrl]);

  return { ...state, approveIncident, dismissIncident };
}
