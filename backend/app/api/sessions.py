"""Session lifecycle endpoints."""

from __future__ import annotations

import chess
import time
from collections import defaultdict
from typing import DefaultDict, List

from fastapi import APIRouter, HTTPException, Path

from ..board import Board
from .. import engine
from ..config import settings
from ..schemas import (
    ClockState,
    CoachSummaryResponse,
    Explanation,
    MoveInsight,
    MoveRequest,
    MoveResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionResponse,
)
from ..store import store
from ..realtime import stream_manager
from ..telemetry import log_event

router = APIRouter(prefix="/sessions", tags=["sessions"])

_coach_rate_usage: DefaultDict[str, List[float]] = defaultdict(list)


def _determine_outcome(board: Board, player_color: str) -> tuple[str, str, str]:
    raw = board.raw
    player_is_white = player_color == "white"
    if raw.is_checkmate():
        loser_is_white = raw.turn == chess.WHITE
        loser_is_player = (loser_is_white and player_is_white) or (not loser_is_white and not player_is_white)
        winner = "engine" if loser_is_player else "player"
        message = "Engine delivered checkmate." if winner == "engine" else "You delivered checkmate!"
        return "checkmate", winner, message
    if raw.is_stalemate():
        return "stalemate", "draw", "Game drawn by stalemate."
    return "resigned", "draw", "Game over."


async def _broadcast_game_over(session_id: str, payload: dict) -> None:
    await stream_manager.broadcast(session_id, {"type": "game_over", "payload": payload})
    log_event(session_id, "game_over", payload)


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    record = store.create_session(payload)
    return record.to_response()


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str = Path(..., description="Session identifier")) -> SessionDetail:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return record.to_detail()


@router.post("/{session_id}/moves", response_model=MoveResponse)
async def make_move(
    payload: MoveRequest,
    session_id: str = Path(..., description="Session identifier"),
) -> MoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    board = Board.from_fen(record.fen)
    clocks = ClockState.model_validate(payload.clock.model_dump())
    player_turn = "w" if record.player_color == "white" else "b"
    engine_turn = "w" if record.engine_color == "white" else "b"
    player_move_snapshot: chess.Board | None = None
    player_move_after: chess.Board | None = None
    player_move_obj: chess.Move | None = None

    if payload.uci:
        if board.active_color != player_turn:
            raise HTTPException(status_code=409, detail="It is not the player's turn.")
        legal_moves = board.legal_moves()
        if payload.uci not in legal_moves:
            raise HTTPException(status_code=400, detail="Illegal move.")
        player_move_obj = chess.Move.from_uci(payload.uci)
        player_move_snapshot = board.raw.copy()
        board.apply_uci(payload.uci)
        player_move_after = board.raw.copy()

        if board.raw.is_checkmate() or board.raw.is_stalemate():
            eval_cp = engine.CHECKMATE_CP if record.player_color == "white" else -engine.CHECKMATE_CP
            if board.raw.is_stalemate():
                eval_cp = 0
            if player_move_snapshot and player_move_after and player_move_obj:
                insight = engine.build_move_insight(
                    player_move_snapshot,
                    player_move_after,
                    player_move_obj,
                    chess.WHITE if record.player_color == "white" else chess.BLACK,
                    "player",
                    record.last_eval_cp,
                    eval_cp,
                    len(record.move_log) + 1,
                )
                record.move_log.append(insight)
                record.last_eval_cp = eval_cp
                log_event(
                    session_id,
                    "player_move",
                    {**insight, "clocks": clocks.model_dump()},
                )
            record.status = "completed"
            record.fen = board.to_fen()
            record.clocks = clocks
            record = store.save(record)
            result, winner, message = _determine_outcome(board, record.player_color)
            explanation = Explanation(
                summary=message,
                objective_cost_cp=0,
                alt_best_move="-",
                alt_eval_cp=0,
            )
            game_state = engine.make_game_state(board)
            response = MoveResponse(
                engine_move=None,
                engine_eval_cp=0,
                exploit_confidence=0.0,
                opponent_profile=record.opponent_profile,
                explanation=explanation,
                game_state=game_state,
                result=result,
                winner=winner,
                message=message,
            )
            await _broadcast_game_over(
                session_id,
                {
                    "result": result,
                    "winner": winner,
                    "message": message,
                    "game_state": game_state.model_dump(),
                    "difficulty": record.difficulty,
                    "engine_depth": record.engine_depth,
                    "engine_rating": record.engine_rating,
                },
            )
            return response

    if board.active_color != engine_turn:
        raise HTTPException(status_code=409, detail="Engine is waiting for the player move.")

    board_before_engine_move = board.copy()
    try:
        engine_move, eval_cp = engine.pick_engine_move(board, record.difficulty, record.engine_rating)
    except ValueError:
        raise HTTPException(status_code=410, detail="Engine has no legal moves (game over).") from None

    player_insight_dict: dict[str, object] | None = None
    if player_move_snapshot and player_move_after and player_move_obj:
        player_insight_dict = engine.build_move_insight(
            player_move_snapshot,
            player_move_after,
            player_move_obj,
            chess.WHITE if record.player_color == "white" else chess.BLACK,
            "player",
            record.last_eval_cp,
            eval_cp,
            len(record.move_log) + 1,
        )
        record.move_log.append(player_insight_dict)
        record.last_eval_cp = eval_cp
        log_event(
            session_id,
            "player_move",
            {**player_insight_dict, "clocks": clocks.model_dump()},
        )

    explanation = engine.explain_engine_move(
        board_before_engine_move,
        engine_move,
        eval_cp,
        record.engine_color,
        (player_insight_dict or {}).get("commentary"),
        record.difficulty,
        record.engine_rating,
    )

    board.apply_uci(engine_move)
    post_engine_eval = engine.evaluate_position(board, record.difficulty, record.engine_rating)
    engine_move_obj = chess.Move.from_uci(engine_move)
    engine_insight = engine.build_move_insight(
        board_before_engine_move.raw,
        board.raw.copy(),
        engine_move_obj,
        chess.WHITE if record.engine_color == "white" else chess.BLACK,
        "engine",
        eval_cp,
        post_engine_eval,
        len(record.move_log) + 1,
    )
    record.move_log.append(engine_insight)
    record.last_eval_cp = post_engine_eval

    profile = engine.mock_opponent_profile()
    record.opponent_profile = profile
    record.fen = board.to_fen()
    record.clocks = clocks

    record = store.save(record)

    exploit_confidence = engine.mock_exploit_confidence()
    game_state = engine.make_game_state(board)

    response = MoveResponse(
        engine_move=engine_move,
        engine_eval_cp=eval_cp,
        exploit_confidence=exploit_confidence,
        opponent_profile=profile,
        explanation=explanation,
        game_state=game_state,
        latest_insight=MoveInsight.model_validate(player_insight_dict) if player_insight_dict else None,
    )

    if board.raw.is_checkmate() or board.raw.is_stalemate():
        record.status = "completed"
        record = store.save(record)
        result, winner, message = _determine_outcome(board, record.player_color)
        response.result = result
        response.winner = winner
        response.message = message
        await _broadcast_game_over(
            session_id,
            {
                "result": result,
                "winner": winner,
                "message": message,
                "game_state": game_state.model_dump(),
                "difficulty": record.difficulty,
                "engine_depth": record.engine_depth,
                "engine_rating": record.engine_rating,
            },
        )

    event_payload = {
        "uci": engine_move,
        "engine_eval_cp": response.engine_eval_cp,
        "exploit_confidence": response.exploit_confidence,
        "best_line": [engine_move, "d2d4", "c5d4"],
        "clocks": record.clocks.model_dump(),
        "game_state": response.game_state.model_dump(),
        "opponent_profile": response.opponent_profile.model_dump(),
        "explanation": response.explanation.model_dump(),
        "result": response.result,
        "winner": response.winner,
        "difficulty": record.difficulty,
        "engine_depth": record.engine_depth,
        "engine_rating": record.engine_rating,
        "history_entry": engine_insight,
    }

    await stream_manager.broadcast(
        session_id,
        {
            "type": "engine_move",
            "payload": event_payload,
        },
    )
    log_event(session_id, "engine_move", event_payload)

    return response


@router.post("/{session_id}/resign", response_model=SessionResponse)
def resign_session(session_id: str) -> SessionResponse:
    try:
        record = store.complete_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    log_event(session_id, "session_resigned", {"status": record.status})
    return record.to_response()


@router.post("/{session_id}/coach", response_model=CoachSummaryResponse)
async def summarize_position(session_id: str = Path(..., description="Session identifier")) -> CoachSummaryResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    _enforce_coach_rate_limit(session_id)
    board = Board.from_fen(record.fen)
    eval_cp = engine.evaluate_position(board, record.difficulty, record.engine_rating)
    player_feedback = None
    if record.move_log:
        player_feedback = record.move_log[-1].get("commentary")
    try:
        summary = engine.generate_coach_summary(
            board,
            eval_cp,
            record.engine_color,
            player_feedback,
            record.difficulty,
            record.engine_rating,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log_event(session_id, "coach_summary_failed", {"error": str(exc)})
        raise HTTPException(status_code=502, detail="Coach summary unavailable.") from exc
    log_event(session_id, "coach_summary", {"length": len(summary or "")})
    return CoachSummaryResponse(summary=summary)


def _enforce_coach_rate_limit(session_id: str) -> None:
    window = settings.coach_rate_limit_window
    max_calls = settings.coach_rate_limit_max
    if not window or not max_calls:
        return
    now = time.time()
    timestamps = _coach_rate_usage[session_id]
    cutoff = now - window
    while timestamps and timestamps[0] < cutoff:
        timestamps.pop(0)
    if len(timestamps) >= max_calls:
        raise HTTPException(status_code=429, detail="Too many coach summaries requested. Please wait.")
    timestamps.append(now)
