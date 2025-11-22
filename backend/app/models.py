"""SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import chess

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    player_color = Column(String, nullable=False)
    engine_color = Column(String, nullable=False)
    exploit_mode = Column(String, nullable=False)
    difficulty = Column(String, nullable=False, default="advanced")
    engine_depth = Column(Integer, default=3, nullable=False)
    engine_rating = Column(Integer, default=1200, nullable=False)
    status = Column(String, default="active", nullable=False)
    result = Column(String, nullable=True)
    winner = Column(String, nullable=True)
    fen = Column(String, nullable=False)
    initial_fen = Column(String, nullable=False, default=chess.STARTING_FEN)
    clock_player_ms = Column(Integer, default=300000, nullable=False)
    clock_engine_ms = Column(Integer, default=300000, nullable=False)
    moves = Column(JSON, default=list, nullable=False)
    opponent_profile = Column(JSON, nullable=False)
    player_white_id = Column(String, nullable=True)
    player_black_id = Column(String, nullable=True)
    player_id = Column(String, nullable=True)
    player_rating = Column(Integer, default=1500, nullable=False)
    player_rating_delta = Column(Integer, default=0, nullable=False)
    is_multiplayer = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "player_color": self.player_color,
            "engine_color": self.engine_color,
            "exploit_mode": self.exploit_mode,
            "engine_depth": self.engine_depth,
            "engine_rating": self.engine_rating,
            "difficulty": self.difficulty,
            "status": self.status,
            "fen": self.fen,
            "initial_fen": self.initial_fen,
            "clock_player_ms": self.clock_player_ms,
            "clock_engine_ms": self.clock_engine_ms,
            "moves": list(self.moves or []),
            "opponent_profile": self.opponent_profile,
            "player_id": self.player_id,
            "player_rating": self.player_rating,
            "player_rating_delta": self.player_rating_delta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class EngineEventModel(Base):
    __tablename__ = "engine_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: uuid4().hex)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    username = Column(String, nullable=False)
    rating_hint = Column(Integer, nullable=True)
    exploit_default = Column(String, nullable=False, default="auto")
    share_data_opt_in = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
