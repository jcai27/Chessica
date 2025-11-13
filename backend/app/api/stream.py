"""WebSocket streaming endpoints."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..realtime import stream_manager
from ..store import store

router = APIRouter()


@router.websocket("/api/v1/sessions/{session_id}/stream")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    try:
        store.get_session(session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await stream_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        stream_manager.disconnect(session_id, websocket)
