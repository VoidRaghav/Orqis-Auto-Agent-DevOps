"""
WebSocket connection manager.

Tracks all active dashboard connections and broadcasts messages to all of them.
Thread-safe within a single asyncio event loop (FastAPI's default).
"""

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, msg_type: str, data: Any) -> None:
        """Send a JSON message to every connected dashboard client."""
        payload = json.dumps({"type": msg_type, "data": data})
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()
