"""Persistent session repository backed by SQLAlchemy + Redis cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import uuid4
import random

import chess

from .cache import session_cache
from .database import SessionLocal
from .models import SessionModel
from .config import settings
from .schemas import (
    ClockState,
    DifficultyLevel,
    MoveInsight,
    OpponentProfile,
    OpponentStyle,
    SessionCreateRequest,
    SessionDetail,
    SessionResponse,
    MultiplayerSessionCreateRequest,
    MultiplayerSessionResponse,
)

DEFAULT_FEN = chess.STARTING_FEN
DIFFICULTY_PRESETS = [
    {"name": "beginner", "rating": 1320, "depth": 1},
    {"name": "intermediate", "rating": 1600, "depth": 2},
    {"name": "advanced", "rating": 2000, "depth": 3},
    {"name": "expert", "rating": 2300, "depth": 4},
    {"name": "grandmaster", "rating": 2600, "depth": 5},
]
DIFFICULTY_MAP = {preset["name"]: preset for preset in DIFFICULTY_PRESETS}
DEPTH_TO_PRESET = {preset["depth"]: preset for preset in DIFFICULTY_PRESETS}


def depth_to_rating(depth: int) -> int:
    preset = DEPTH_TO_PRESET.get(depth)
    if preset:
        return preset["rating"]
    return 600 + depth * 400


def rating_to_preset(rating: int) -> dict:
    return min(DIFFICULTY_PRESETS, key=lambda preset: abs(preset["rating"] - rating))


def resolve_engine_settings(payload: SessionCreateRequest) -> tuple[int, int, DifficultyLevel]:
    if payload.difficulty and payload.difficulty in DIFFICULTY_MAP:
        preset = DIFFICULTY_MAP[payload.difficulty]
        return preset["depth"], preset["rating"], payload.difficulty
    if payload.engine_rating:
        preset = rating_to_preset(payload.engine_rating)
        return preset["depth"], payload.engine_rating, preset["name"]
    if payload.engine_depth:
        depth = payload.engine_depth
        preset = DEPTH_TO_PRESET.get(depth)
        rating = preset["rating"] if preset else depth_to_rating(depth)
        difficulty: DifficultyLevel = preset["name"] if preset else "custom"
        return depth, rating, difficulty
    default_depth = settings.engine_default_depth
    preset = DEPTH_TO_PRESET.get(default_depth, DIFFICULTY_PRESETS[2])
    return preset["depth"], preset["rating"], preset["name"]


@dataclass
class SessionRecord:
    session_id: str
    player_color: str
    engine_color: str
    exploit_mode: str
    status: str
    created_at: datetime
    updated_at: datetime
    fen: str
    initial_fen: str = DEFAULT_FEN
    clocks: ClockState
    move_log: List[Dict[str, Any]] = field(default_factory=list)
    opponent_profile: OpponentProfile = field(
        default_factory=lambda: OpponentProfile(
            style=OpponentStyle(tactical=0.5, risk=0.5),
            motif_risk={"forks": 0.4, "back_rank": 0.3},
        )
    )
    player_white_id: str | None = None
    player_black_id: str | None = None
    is_multiplayer: bool = False
    result: str | None = None
    winner: str | None = None
    engine_depth: int = settings.engine_default_depth
    engine_rating: int = field(default_factory=lambda: depth_to_rating(settings.engine_default_depth))
    difficulty: DifficultyLevel = field(
        default_factory=lambda: DEPTH_TO_PRESET.get(settings.engine_default_depth, DIFFICULTY_PRESETS[2])["name"]
    )
    last_eval_cp: int = 0

    def to_response(self) -> SessionResponse:
        return SessionResponse(
            session_id=self.session_id,
            engine_color=self.engine_color,
            player_color=self.player_color,
            exploit_mode=self.exploit_mode,
            engine_depth=self.engine_depth,
            engine_rating=self.engine_rating,
            difficulty=self.difficulty,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_detail(self) -> SessionDetail:
        simple_moves = [entry.get("uci", "") for entry in self.move_log]
        history_models: list[MoveInsight] = []
        for entry in self.move_log:
            if not entry.get("uci") or "verdict" not in entry:
                continue
            history_models.append(MoveInsight.model_validate(entry))
        return SessionDetail(
            **self.to_response().model_dump(),
            fen=self.fen,
            clocks=self.clocks,
            moves=simple_moves,
            history=history_models,
            opponent_profile=self.opponent_profile,
            is_multiplayer=self.is_multiplayer,
            player_white_id=self.player_white_id,
            player_black_id=self.player_black_id,
        )

    def to_multiplayer_response(self) -> MultiplayerSessionResponse:
        return MultiplayerSessionResponse(
            session_id=self.session_id,
            player_white_id=self.player_white_id,
            player_black_id=self.player_black_id,
            status=self.status,
            fen=self.fen,
            clocks=self.clocks,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_cache(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "player_color": self.player_color,
            "engine_color": self.engine_color,
            "exploit_mode": self.exploit_mode,
            "status": self.status,
            "result": self.result,
            "winner": self.winner,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "fen": self.fen,
            "clocks": self.clocks.model_dump(),
            "moves": self.move_log,
            "opponent_profile": self.opponent_profile.model_dump(),
            "initial_fen": self.initial_fen,
            "engine_depth": self.engine_depth,
            "engine_rating": self.engine_rating,
            "difficulty": self.difficulty,
            "last_eval_cp": self.last_eval_cp,
            "player_white_id": self.player_white_id,
            "player_black_id": self.player_black_id,
            "is_multiplayer": self.is_multiplayer,
        }

    @classmethod
    def from_cache(cls, payload: Dict[str, Any]) -> "SessionRecord":
        return cls(
            session_id=payload["session_id"],
            player_color=payload["player_color"],
            engine_color=payload["engine_color"],
            exploit_mode=payload["exploit_mode"],
            status=payload["status"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            fen=payload["fen"],
            initial_fen=payload.get("initial_fen", DEFAULT_FEN),
            clocks=ClockState.model_validate(payload["clocks"]),
            move_log=_normalize_moves(payload.get("moves", [])),
            opponent_profile=OpponentProfile.model_validate(payload["opponent_profile"]),
            engine_depth=payload.get("engine_depth", settings.engine_default_depth),
            engine_rating=payload.get("engine_rating", depth_to_rating(settings.engine_default_depth)),
            difficulty=payload.get("difficulty", "advanced"),
            last_eval_cp=payload.get("last_eval_cp", 0),
            player_white_id=payload.get("player_white_id"),
            player_black_id=payload.get("player_black_id"),
            is_multiplayer=payload.get("is_multiplayer", False),
            result=payload.get("result"),
            winner=payload.get("winner"),
        )

    @classmethod
    def from_model(cls, model: SessionModel) -> "SessionRecord":
        move_log = _normalize_moves(model.moves or [])
        last_eval = 0
        for entry in reversed(move_log):
            if isinstance(entry, dict) and "eval_cp" in entry:
                last_eval = entry.get("eval_cp", 0)
                break
        return cls(
            session_id=model.session_id,
            player_color=model.player_color,
            engine_color=model.engine_color,
            exploit_mode=model.exploit_mode,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
            fen=model.fen,
            initial_fen=getattr(model, "initial_fen", DEFAULT_FEN),
            clocks=ClockState(player_ms=model.clock_player_ms, engine_ms=model.clock_engine_ms),
            move_log=move_log,
            opponent_profile=OpponentProfile.model_validate(model.opponent_profile),
            engine_depth=model.engine_depth,
            engine_rating=model.engine_rating,
            difficulty=model.difficulty or "custom",
            last_eval_cp=last_eval,
            player_white_id=model.player_white_id,
            player_black_id=model.player_black_id,
            is_multiplayer=bool(model.is_multiplayer),
            result=model.result,
            winner=model.winner,
        )

    @property
    def moves(self) -> List[str]:
        return [entry.get("uci", "") for entry in self.move_log]


def _normalize_moves(raw_moves: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not raw_moves:
        return normalized
    for item in raw_moves:
        if isinstance(item, str):
            normalized.append({"uci": item})
        else:
            normalized.append(dict(item))
    return normalized


class SessionRepository:
    def __init__(self) -> None:
        self.cache = session_cache

    def create_session(self, payload: SessionCreateRequest) -> SessionRecord:
        session_id = f"sess_{uuid4().hex}"
        player_color, engine_color = self._resolve_colors(payload.color)
        depth, rating, difficulty = resolve_engine_settings(payload)
        record = SessionRecord(
            session_id=session_id,
            player_color=player_color,
            engine_color=engine_color,
            exploit_mode=payload.exploit_mode,
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            fen=DEFAULT_FEN,
            initial_fen=DEFAULT_FEN,
            clocks=ClockState(player_ms=payload.time_control.initial_ms, engine_ms=payload.time_control.initial_ms),
            engine_depth=depth,
            engine_rating=rating,
            difficulty=difficulty,
        )
        record.opponent_profile = OpponentProfile(
            style=OpponentStyle(tactical=0.5, risk=0.5),
            motif_risk={"forks": 0.4, "back_rank": 0.3},
        )

        with SessionLocal() as db:
            db_model = SessionModel(
                session_id=record.session_id,
                player_color=record.player_color,
                engine_color=record.engine_color,
                exploit_mode=record.exploit_mode,
                difficulty=record.difficulty,
                engine_rating=record.engine_rating,
                status=record.status,
                fen=record.fen,
                initial_fen=record.initial_fen,
                clock_player_ms=record.clocks.player_ms,
                clock_engine_ms=record.clocks.engine_ms,
                moves=list(record.move_log),
                opponent_profile=record.opponent_profile.model_dump(),
                created_at=record.created_at,
                updated_at=record.updated_at,
                engine_depth=record.engine_depth,
                is_multiplayer=False,
            )
            db.add(db_model)
            db.commit()
        self.cache.set(record.session_id, record.to_cache())
        return record

    def create_multiplayer_session(self, payload: MultiplayerSessionCreateRequest) -> SessionRecord:
        session_id = f"sess_{uuid4().hex}"
        white_id = payload.player_white_id
        black_id = payload.player_black_id

        if payload.color == "white" and not white_id and black_id:
            white_id, black_id = black_id, white_id
        elif payload.color == "black" and not black_id and white_id:
            black_id, white_id = white_id, black_id
        elif payload.color == "auto" and white_id and black_id and random.choice([True, False]):
            white_id, black_id = black_id, white_id

        record = SessionRecord(
            session_id=session_id,
            player_color="white",
            engine_color="black",
            exploit_mode="off",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            fen=payload.seed_fen or DEFAULT_FEN,
            initial_fen=payload.seed_fen or DEFAULT_FEN,
            clocks=ClockState(player_ms=payload.time_control.initial_ms, engine_ms=payload.time_control.initial_ms),
            difficulty="advanced",
            engine_depth=settings.engine_default_depth,
            engine_rating=depth_to_rating(settings.engine_default_depth),
            player_white_id=white_id,
            player_black_id=black_id,
            is_multiplayer=True,
        )

        record.opponent_profile = OpponentProfile(
            style=OpponentStyle(tactical=0.5, risk=0.5),
            motif_risk={"forks": 0.4, "back_rank": 0.3},
        )

        with SessionLocal() as db:
            db_model = SessionModel(
                session_id=record.session_id,
                player_color=record.player_color,
                engine_color=record.engine_color,
                exploit_mode=record.exploit_mode,
                difficulty=record.difficulty,
                engine_rating=record.engine_rating,
                status=record.status,
                fen=record.fen,
                initial_fen=record.initial_fen,
                clock_player_ms=record.clocks.player_ms,
                clock_engine_ms=record.clocks.engine_ms,
                moves=list(record.move_log),
                opponent_profile=record.opponent_profile.model_dump(),
                created_at=record.created_at,
                updated_at=record.updated_at,
                engine_depth=record.engine_depth,
                player_white_id=record.player_white_id,
                player_black_id=record.player_black_id,
                is_multiplayer=True,
            )
            db.add(db_model)
            db.commit()
        self.cache.set(record.session_id, record.to_cache())
        return record

    def get_session(self, session_id: str) -> SessionRecord:
        cached = self.cache.get(session_id)
        if cached:
            return SessionRecord.from_cache(cached)
        with SessionLocal() as db:
            model = db.get(SessionModel, session_id)
            if not model:
                raise KeyError(session_id)
            record = SessionRecord.from_model(model)
        self.cache.set(session_id, record.to_cache())
        return record

    def save(self, record: SessionRecord) -> SessionRecord:
        with SessionLocal() as db:
            model = db.get(SessionModel, record.session_id)
            if not model:
                raise KeyError(record.session_id)
            model.status = record.status
            model.fen = record.fen
            model.initial_fen = record.initial_fen
            model.clock_player_ms = record.clocks.player_ms
            model.clock_engine_ms = record.clocks.engine_ms
            model.moves = list(record.move_log)
            model.opponent_profile = record.opponent_profile.model_dump()
            model.engine_depth = record.engine_depth
            model.engine_rating = record.engine_rating
            model.difficulty = record.difficulty
            model.player_white_id = record.player_white_id
            model.player_black_id = record.player_black_id
            model.is_multiplayer = record.is_multiplayer
            model.result = record.result
            model.winner = record.winner
            model.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(model)
            updated_record = SessionRecord.from_model(model)
        self.cache.set(record.session_id, updated_record.to_cache())
        return updated_record

    def complete_session(self, session_id: str) -> SessionRecord:
        with SessionLocal() as db:
            model = db.get(SessionModel, session_id)
            if not model:
                raise KeyError(session_id)
            model.status = "completed"
            model.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(model)
            record = SessionRecord.from_model(model)
        self.cache.set(session_id, record.to_cache())
        return record

    @staticmethod
    def _resolve_colors(requested: str) -> tuple[str, str]:
        if requested == "auto":
            requested = "white"
        player_color = requested
        engine_color = "black" if player_color == "white" else "white"
        return player_color, engine_color


store = SessionRepository()
