"""Multiplayer session endpoints (human vs human)."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Optional

import chess
from fastapi import APIRouter, HTTPException, Path

from ..board import Board
from .. import engine
from ..config import settings
from ..schemas import (
    ClockState,
    GameState,
    MoveInsight,
    MultiplayerMoveRequest,
    MultiplayerMoveResponse,
    MultiplayerSessionCreateRequest,
    MultiplayerSessionResponse,
    QueueJoinRequest,
    QueueStatusResponse,
)
from ..store import store
from ..realtime import stream_manager
from ..telemetry import log_event

router = APIRouter(prefix="/multiplayer", tags=["multiplayer"])
matchmaking_queue: dict[str, dict] = {}
matched_sessions: dict[str, dict] = {}
try:
    import redis  # type: ignore
except ImportError:
    redis = None

_redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1) if settings.redis_url and redis else None


def _queue_list_key(bucket: str) -> str:
    return f"mm:bucket:{bucket}"


def _queue_entry_key(player_id: str) -> str:
    return f"mm:queue:{player_id}"


def _match_key(player_id: str) -> str:
    return f"mm:matched:{player_id}"


def _bucket(time_control: ClockState) -> str:
    return f"{time_control.initial_ms}:{time_control.increment_ms}"


_MATERIAL_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def _quick_material_eval(board: chess.Board) -> int:
    """Lightweight eval to avoid blocking on Stockfish for multiplayer moves."""
    score = 0
    for piece_type, value in _MATERIAL_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value
    return score


def _pop_match(player_id: str, bucket: str, preferred_color: str) -> Optional[dict]:
    if _redis_client:
        candidates = _redis_client.lrange(_queue_list_key(bucket), 0, -1)
        for candidate_id in candidates:
            if candidate_id == player_id:
                continue
            entry = _redis_client.hgetall(_queue_entry_key(candidate_id))
            if not entry:
                continue
            if entry.get("color") and preferred_color != "auto" and entry["color"] == preferred_color != "auto":
                continue
            _redis_client.lrem(_queue_list_key(bucket), 0, candidate_id)
            _redis_client.delete(_queue_entry_key(candidate_id))
            return {
                "bucket": bucket,
                "color": entry.get("color", "auto"),
                "player_id": candidate_id,
                "time_control": json.loads(entry.get("time_control") or "{}"),
            }
    for other_id, info in list(matchmaking_queue.items()):
        if info["bucket"] != bucket or other_id == player_id:
            continue
        if info["color"] != "auto" and preferred_color != "auto" and info["color"] == preferred_color:
            continue
        matchmaking_queue.pop(other_id, None)
        return info
    return None


def _assign_colors(requester: str, preferred_color: str, opponent: dict) -> tuple[str, str, str]:
    opponent_id = opponent["player_id"]
    opponent_color = opponent.get("color", "auto")

    if preferred_color == "white" or opponent_color == "black":
        return requester, opponent_id, "white"
    if preferred_color == "black" or opponent_color == "white":
        return opponent_id, requester, "black"
    if random.choice([True, False]):
        return requester, opponent_id, "white"
    return opponent_id, requester, "black"


@router.post("/sessions", response_model=MultiplayerSessionResponse, status_code=201)
def create_multiplayer_session(payload: MultiplayerSessionCreateRequest) -> MultiplayerSessionResponse:
    record = store.create_multiplayer_session(payload)
    return record.to_multiplayer_response()


@router.post("/queue", response_model=QueueStatusResponse)
def join_queue(payload: QueueJoinRequest) -> QueueStatusResponse:
    bucket = _bucket(payload.time_control)
    match = _pop_match(payload.player_id, bucket, payload.color)
    if match:
        white_id, black_id, player_color = _assign_colors(payload.player_id, payload.color, match)
        time_control = match.get("time_control") or payload.time_control.model_dump()
        session = store.create_multiplayer_session(
            MultiplayerSessionCreateRequest(
                player_white_id=white_id,
                player_black_id=black_id,
                time_control=time_control,
                color="auto",
            )
        )
        requester_payload = {
            "status": "matched",
            "session_id": session.session_id,
            "player_color": "white" if player_color == "white" else "black",
            "opponent_id": match["player_id"],
        }
        opponent_payload = {
            "status": "matched",
            "session_id": session.session_id,
            "player_color": "black" if player_color == "white" else "white",
            "opponent_id": payload.player_id,
        }
        matched_sessions[payload.player_id] = requester_payload
        matched_sessions[match["player_id"]] = opponent_payload
        if _redis_client:
            _redis_client.setex(_match_key(payload.player_id), 3600, json.dumps(requester_payload))
            _redis_client.setex(_match_key(match["player_id"]), 3600, json.dumps(opponent_payload))
        return QueueStatusResponse(**requester_payload)

    entry = {
        "bucket": bucket,
        "color": payload.color,
        "player_id": payload.player_id,
        "time_control": payload.time_control.model_dump(),
    }
    if _redis_client:
        _redis_client.hset(
            _queue_entry_key(payload.player_id),
            mapping={
                "bucket": bucket,
                "color": payload.color,
                "player_id": payload.player_id,
                "time_control": json.dumps(payload.time_control.model_dump()),
            },
        )
        _redis_client.expire(_queue_entry_key(payload.player_id), 3600)
        _redis_client.rpush(_queue_list_key(bucket), payload.player_id)
    matchmaking_queue[payload.player_id] = entry
    return QueueStatusResponse(status="queued", message="Waiting for an opponent.")


@router.delete("/queue/{player_id}", response_model=QueueStatusResponse)
def leave_queue(player_id: str) -> QueueStatusResponse:
    entry = matchmaking_queue.pop(player_id, None)
    matched_sessions.pop(player_id, None)
    if _redis_client:
        redis_entry = _redis_client.hgetall(_queue_entry_key(player_id))
        bucket = redis_entry.get("bucket") if redis_entry else (entry or {}).get("bucket")
        _redis_client.delete(_queue_entry_key(player_id))
        _redis_client.delete(_match_key(player_id))
        if bucket:
            _redis_client.lrem(_queue_list_key(bucket), 0, player_id)
    return QueueStatusResponse(status="none", message="Left queue.")


@router.get("/queue/{player_id}", response_model=QueueStatusResponse)
def queue_status(player_id: str) -> QueueStatusResponse:
    if _redis_client:
        match_raw = _redis_client.getdel(_match_key(player_id))
        if match_raw:
            try:
                payload = json.loads(match_raw)
                return QueueStatusResponse(**payload)
            except Exception:
                pass
    if player_id in matched_sessions:
        payload = matched_sessions.pop(player_id)
        return QueueStatusResponse(**payload)
    if player_id in matchmaking_queue:
        return QueueStatusResponse(status="queued", message="Still waiting.")
    return QueueStatusResponse(status="none")


@router.post("/sessions/{session_id}/moves", response_model=MultiplayerMoveResponse)
async def play_move(
    payload: MultiplayerMoveRequest,
    session_id: str = Path(..., description="Session identifier"),
) -> MultiplayerMoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not record.is_multiplayer:
        raise HTTPException(status_code=409, detail="Session is not multiplayer.")

    board = Board.from_fen(record.fen)

    mover_color = "white" if board.raw.turn == chess.WHITE else "black"
    expected_player = record.player_white_id if mover_color == "white" else record.player_black_id
    if expected_player and payload.player_id != expected_player:
        raise HTTPException(status_code=403, detail="It is not your turn.")

    if payload.uci not in board.legal_moves():
        raise HTTPException(status_code=400, detail="Illegal move.")

    move_obj = chess.Move.from_uci(payload.uci)
    before = board.raw.copy(stack=True)
    board.apply_uci(payload.uci)
    after = board.raw.copy(stack=True)

    # Clock handling: deduct elapsed from mover based on last update.
    now = datetime.now(timezone.utc)
    elapsed_ms = 0
    if record.updated_at:
        elapsed_ms = max(0, int((now - record.updated_at).total_seconds() * 1000))
    clocks = record.clocks.model_dump()
    if mover_color == "white":
        clocks["player_ms"] = max(0, clocks.get("player_ms", 0) - elapsed_ms)
    else:
        clocks["engine_ms"] = max(0, clocks.get("engine_ms", 0) - elapsed_ms)
    record.clocks = ClockState.model_validate(clocks)

    prev_eval = record.last_eval_cp
    if board.raw.is_checkmate():
        eval_cp = engine.CHECKMATE_CP if mover_color == "white" else -engine.CHECKMATE_CP
    elif board.raw.is_stalemate():
        eval_cp = 0
    else:
        eval_cp = _quick_material_eval(board.raw)

    insight_dict = engine.build_move_insight(
        before,
        after,
        move_obj,
        chess.WHITE if mover_color == "white" else chess.BLACK,
        "player",
        prev_eval,
        eval_cp,
        len(record.move_log) + 1,
    )
    record.move_log.append(insight_dict)
    record.last_eval_cp = eval_cp

    record.fen = board.to_fen()
    record.updated_at = now

    result = None
    winner = None
    message = None
    if board.raw.is_checkmate() or board.raw.is_stalemate():
        record.status = "completed"
        result, winner, message = (
            ("checkmate", "white" if board.raw.turn == chess.BLACK else "black", "Checkmate.")
            if board.raw.is_checkmate()
            else ("stalemate", "draw", "Game drawn by stalemate.")
        )
        record.result = result
        record.winner = winner

    record = store.save(record)
    game_state = GameState(
        fen=record.fen,
        move_number=board.fullmove,
        turn="white" if board.raw.turn == chess.WHITE else "black",
    )

    response = MultiplayerMoveResponse(
        move_uci=payload.uci,
        eval_cp=eval_cp,
        game_state=game_state,
        latest_insight=MoveInsight.model_validate(insight_dict),
        result=result,
        winner=winner,
        message=message,
        clocks=record.clocks,
    )

    event_payload = {
        "uci": payload.uci,
        "game_state": game_state.model_dump(),
        "eval_cp": eval_cp,
        "latest_insight": insight_dict,
        "result": result,
        "winner": winner,
        "message": message,
        "player": payload.player_id,
        "clocks": record.clocks.model_dump(),
    }
    await stream_manager.broadcast(session_id, {"type": "player_move", "payload": event_payload})
    log_event(session_id, "player_move", event_payload)

    return response


@router.post("/sessions/{session_id}/resign", response_model=MultiplayerMoveResponse)
async def resign(
    session_id: str = Path(..., description="Session identifier"),
) -> MultiplayerMoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not record.is_multiplayer:
        raise HTTPException(status_code=409, detail="Session is not multiplayer.")
    record.status = "completed"
    record.result = "resigned"
    record.winner = "white" if record.player_color == "black" else "black"
    record = store.save(record)
    game_state = GameState(
        fen=record.fen,
        move_number=Board.from_fen(record.fen).fullmove,
        turn="white",
    )
    payload = {
        "result": record.result,
        "winner": record.winner,
        "message": "Player resigned.",
        "game_state": game_state.model_dump(),
    }
    await stream_manager.broadcast(session_id, {"type": "game_over", "payload": payload})
    log_event(session_id, "game_over", payload)
    return MultiplayerMoveResponse(
        move_uci="resign",
        eval_cp=record.last_eval_cp,
        game_state=game_state,
        result=record.result,
        winner=record.winner,
        message="Player resigned.",
        clocks=record.clocks,
    )


@router.post("/sessions/{session_id}/draw", response_model=MultiplayerMoveResponse)
async def offer_draw(session_id: str = Path(..., description="Session identifier")) -> MultiplayerMoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not record.is_multiplayer:
        raise HTTPException(status_code=409, detail="Session is not multiplayer.")
    record.status = "completed"
    record.result = "draw"
    record.winner = "draw"
    record = store.save(record)
    game_state = GameState(
        fen=record.fen,
        move_number=Board.from_fen(record.fen).fullmove,
        turn="white",
    )
    payload = {
        "result": record.result,
        "winner": record.winner,
        "message": "Game drawn by agreement.",
        "game_state": game_state.model_dump(),
    }
    await stream_manager.broadcast(session_id, {"type": "game_over", "payload": payload})
    log_event(session_id, "game_over", payload)
    return MultiplayerMoveResponse(
        move_uci="draw",
        eval_cp=record.last_eval_cp,
        game_state=game_state,
        result=record.result,
        winner=record.winner,
        message="Game drawn by agreement.",
        clocks=record.clocks,
    )


@router.post("/sessions/{session_id}/abort", response_model=MultiplayerMoveResponse)
async def abort_session(session_id: str = Path(..., description="Session identifier")) -> MultiplayerMoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not record.is_multiplayer:
        raise HTTPException(status_code=409, detail="Session is not multiplayer.")
    record.status = "abandoned"
    record.result = "abandoned"
    record.winner = None
    record = store.save(record)
    game_state = GameState(
        fen=record.fen,
        move_number=Board.from_fen(record.fen).fullmove,
        turn="white",
    )
    payload = {
        "result": record.result,
        "winner": record.winner,
        "message": "Game aborted.",
        "game_state": game_state.model_dump(),
    }
    await stream_manager.broadcast(session_id, {"type": "game_over", "payload": payload})
    log_event(session_id, "game_over", payload)
    return MultiplayerMoveResponse(
        move_uci="abort",
        eval_cp=record.last_eval_cp,
        game_state=game_state,
        result=record.result,
        winner=record.winner,
        message="Game aborted.",
        clocks=record.clocks,
    )
