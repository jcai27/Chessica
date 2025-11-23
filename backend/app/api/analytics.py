"""Analytics endpoints for engine events."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Path

from ..database import SessionLocal
from ..models import EngineEventModel, SessionModel
from ..schemas import EngineEvent, EngineEventResponse, EngineEventSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/sessions/{session_id}/events", response_model=EngineEventResponse)
def get_session_events(session_id: str = Path(..., description="Session identifier")) -> EngineEventResponse:
    with SessionLocal() as db:
        session = db.get(SessionModel, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        events = (
            db.query(EngineEventModel)
            .filter(EngineEventModel.session_id == session_id)
            .order_by(EngineEventModel.created_at.asc())
            .all()
        )

    event_items = [
        EngineEvent(
            id=event.id,
            session_id=event.session_id,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event in events
    ]

    counts = Counter(event.event_type for event in event_items)
    summary = EngineEventSummary(
        total_events=len(event_items),
        counts_by_type=dict(counts),
        last_event_at=event_items[-1].created_at if event_items else None,
    )
    return EngineEventResponse(session_id=session_id, events=event_items, summary=summary)


@router.get("/profile/{user_id}")
def get_profile_history(user_id: str = Path(..., description="User identifier")) -> dict:
    """Get the current opponent profile for a user."""
    from ..opponent_model import ProfileService
    
    with SessionLocal() as db:
        service = ProfileService(db)
        profile = service.get_profile(user_id)
        return profile


@router.get("/stats/{user_id}")
def get_user_stats(user_id: str = Path(..., description="User identifier")) -> dict:
    """Get aggregate statistics for a user."""
    with SessionLocal() as db:
        # Win rate
        sessions = db.query(SessionModel).filter(SessionModel.player_id == user_id).all()
        total_games = len(sessions)
        if not total_games:
            return {"win_rate": 0, "total_games": 0, "recent_results": []}
            
        wins = sum(1 for s in sessions if s.winner == "player")
        losses = sum(1 for s in sessions if s.winner == "engine")
        draws = total_games - wins - losses
        
        # Recent results (last 10)
        recent = [s.winner for s in sorted(sessions, key=lambda x: x.created_at, reverse=True)[:10]]
        
        return {
            "total_games": total_games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "win_rate": round(wins / total_games, 2),
            "recent_results": recent
        }
