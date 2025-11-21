"""Pydantic schemas for Chessica API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, EmailStr


class TimeControl(BaseModel):
    initial_ms: int = Field(..., ge=0)
    increment_ms: int = Field(..., ge=0)


DifficultyLevel = Literal["beginner", "intermediate", "advanced", "expert", "grandmaster", "custom"]


class SessionCreateRequest(BaseModel):
    variant: Literal["standard"] = "standard"
    time_control: TimeControl
    color: Literal["white", "black", "auto"] = "auto"
    exploit_mode: Literal["auto", "on", "off"] = "auto"
    engine_depth: Optional[int] = Field(None, ge=1, le=5)
    difficulty: Optional[DifficultyLevel] = None
    engine_rating: Optional[int] = Field(None, ge=600, le=2800)


class SessionResponse(BaseModel):
    session_id: str
    engine_color: Literal["white", "black"]
    player_color: Literal["white", "black"]
    exploit_mode: Literal["auto", "on", "off"]
    engine_depth: int
    difficulty: DifficultyLevel
    engine_rating: int
    player_rating: int | None = None
    player_rating_delta: int = 0
    status: Literal["active", "completed", "abandoned"]
    created_at: datetime
    updated_at: datetime


class ClockState(BaseModel):
    player_ms: int
    engine_ms: int


class MoveRequest(BaseModel):
    uci: Optional[str] = None
    client_ts: datetime
    clock: ClockState
    player_id: Optional[str] = None
    telemetry: dict | None = None


class OpponentStyle(BaseModel):
    tactical: float = Field(..., ge=0.0, le=1.0)
    risk: float = Field(..., ge=0.0, le=1.0)


class OpponentProfile(BaseModel):
    style: OpponentStyle
    motif_risk: dict[str, float]


class Explanation(BaseModel):
    summary: str
    objective_cost_cp: int
    alt_best_move: str
    alt_eval_cp: int


class MoveInsight(BaseModel):
    ply: int
    side: Literal["player", "engine"]
    uci: str
    san: str
    eval_cp: int
    delta_cp: int
    verdict: Literal["brilliant", "great", "good", "inaccuracy", "mistake", "blunder", "sharp"]
    commentary: str
    themes: list[str] = []
    timestamp: datetime


class GameState(BaseModel):
    fen: str
    move_number: int
    turn: Literal["white", "black"]


class MoveResponse(BaseModel):
    engine_move: str | None = None
    engine_eval_cp: int
    exploit_confidence: float
    opponent_profile: OpponentProfile
    explanation: Explanation
    game_state: GameState
    result: Literal["checkmate", "stalemate", "resigned"] | None = None
    winner: Literal["player", "engine", "draw"] | None = None
    latest_insight: MoveInsight | None = None
    message: str | None = None
    player_rating: int | None = None
    player_rating_delta: int | None = None


class CoachSummaryResponse(BaseModel):
    summary: str


class ReplayMove(BaseModel):
    ply: int
    side: Literal["player", "engine", "white", "black"]
    san: str
    uci: str


class ReplayResponse(BaseModel):
    session_id: str
    player_color: Literal["white", "black"]
    engine_color: Literal["white", "black"]
    status: Literal["active", "completed", "abandoned"]
    result: Literal["checkmate", "stalemate", "resigned"] | None = None
    winner: Literal["player", "engine", "draw"] | None = None
    initial_fen: str
    moves: list[ReplayMove]
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionResponse):
    fen: str
    clocks: ClockState
    moves: list[str]
    history: list[MoveInsight] = []
    opponent_profile: OpponentProfile
    is_multiplayer: bool = False
    player_white_id: Optional[str] = None
    player_black_id: Optional[str] = None


class AnalysisMove(BaseModel):
    ply: int
    player_move: str
    engine_reply: str
    objective_eval_cp: int
    exploit_gain_cp: int
    motifs: list[str]
    explanation: str


class AnalysisSummary(BaseModel):
    induced_blunders: int
    eval_tradeoff_cp: int
    themes: list[str]


class AnalysisResponse(BaseModel):
    session_id: str
    moves: list[AnalysisMove]
    summary: AnalysisSummary


class MultiplayerSessionCreateRequest(BaseModel):
    player_white_id: Optional[str] = None
    player_black_id: Optional[str] = None
    time_control: TimeControl
    color: Literal["auto", "white", "black"] = "auto"
    seed_fen: Optional[str] = None


class MultiplayerSessionResponse(BaseModel):
    session_id: str
    player_white_id: Optional[str] = None
    player_black_id: Optional[str] = None
    status: Literal["active", "completed", "abandoned"]
    fen: str
    clocks: ClockState
    created_at: datetime
    updated_at: datetime


class MultiplayerMoveRequest(BaseModel):
    uci: str
    player_id: str
    client_ts: datetime
    clock: ClockState | None = None


class MultiplayerMoveResponse(BaseModel):
    move_uci: str
    eval_cp: int
    game_state: GameState
    latest_insight: MoveInsight | None = None
    result: Literal["checkmate", "stalemate", "resigned"] | None = None
    winner: Literal["white", "black", "draw"] | None = None
    message: str | None = None
    clocks: ClockState | None = None


class QueueJoinRequest(BaseModel):
    player_id: str
    time_control: TimeControl
    color: Literal["auto", "white", "black"] = "auto"


class QueueStatusResponse(BaseModel):
    status: Literal["queued", "matched", "none"]
    session_id: Optional[str] = None
    player_color: Optional[Literal["white", "black"]] = None
    opponent_id: Optional[str] = None
    message: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    rating_hint: int | None = None
    exploit_default: Literal["auto", "on", "off"] = "auto"
    share_data_opt_in: bool = True


class PreferencesUpdateRequest(BaseModel):
    exploit_default: Literal["auto", "on", "off"] | None = None
    share_data_opt_in: Optional[bool] = None


class EngineEvent(BaseModel):
    id: int
    session_id: str
    event_type: str
    payload: dict
    created_at: datetime


class EngineEventSummary(BaseModel):
    total_events: int
    counts_by_type: dict[str, int]
    last_event_at: datetime | None = None


class EngineEventResponse(BaseModel):
    session_id: str
    events: list[EngineEvent]
    summary: EngineEventSummary


class AuthFeatureResponse(BaseModel):
    enabled: bool


class SendCodeRequest(BaseModel):
    email: EmailStr


class AuthSignInRequest(BaseModel):
    email: EmailStr
    code: str


class AuthSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    remember: bool = False


class AuthTokenResponse(BaseModel):
    token: str
    user: UserResponse
