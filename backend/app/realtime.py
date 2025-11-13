"""Lightweight WebSocket connection manager for session streams."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Set

from fastapi import WebSocket


class SessionStreamManager:
    def __init__(self) -> None:
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if websocket in self._connections.get(session_id, set()):
            self._connections[session_id].remove(websocket)
        if not self._connections.get(session_id):
            self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in self._connections.get(session_id, set()).copy():
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(session_id, websocket)


stream_manager = SessionStreamManager()
