"""WebSocket fan-out so every open browser updates without refreshing."""
import json
from typing import Any

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, kind: str, data: Any) -> None:
        msg = json.dumps({"type": kind, "data": data})
        for ws in list(self._clients):
            try:
                await ws.send_text(msg)
            except Exception:
                self._clients.discard(ws)


hub = Hub()
