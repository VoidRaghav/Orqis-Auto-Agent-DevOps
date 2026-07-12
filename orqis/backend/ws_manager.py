"""
WebSocket connection manager — per-workspace rooms when multi-tenant.
"""

import json
from typing import Any, Optional

from fastapi import WebSocket

from .. import config
from .tenancy import get_workspace_id


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._ws_workspace: dict[int, str] = {}

    async def connect(self, ws: WebSocket, workspace_id: Optional[str] = None) -> None:
        await ws.accept()
        wid = workspace_id or get_workspace_id()
        self._connections.setdefault(wid, []).append(ws)
        self._ws_workspace[id(ws)] = wid

    def disconnect(self, ws: WebSocket) -> None:
        wid = self._ws_workspace.pop(id(ws), None)
        if wid and wid in self._connections:
            try:
                self._connections[wid].remove(ws)
            except ValueError:
                pass
            if not self._connections[wid]:
                del self._connections[wid]

    async def broadcast(
        self,
        msg_type: str,
        data: Any,
        workspace_id: Optional[str] = None,
    ) -> None:
        """Send a JSON message to dashboards in the active or given workspace."""
        wid = workspace_id or get_workspace_id()
        payload = json.dumps({"type": msg_type, "data": data})
        targets = self._connections.get(wid, [])
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


manager = ConnectionManager()
