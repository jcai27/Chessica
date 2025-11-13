"""Event logging helpers."""

from __future__ import annotations

from .database import SessionLocal
from .models import EngineEventModel


def log_event(session_id: str, event_type: str, payload: dict) -> None:
    with SessionLocal() as db:
        db.add(EngineEventModel(session_id=session_id, event_type=event_type, payload=payload))
        db.commit()
