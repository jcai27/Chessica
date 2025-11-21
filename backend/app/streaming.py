"""Simple streaming utilities for pushing analysis/coach updates."""

from __future__ import annotations

from typing import Callable

from .realtime import stream_manager

async def stream_update(session_id: str, payload: dict) -> None:
    await stream_manager.broadcast(session_id, payload)

def streamer(event_type: str) -> Callable[[str, dict], None]:
    async def _wrapper(session_id: str, payload: dict) -> None:
        await stream_update(session_id, {"type": event_type, "payload": payload})
    return _wrapper
