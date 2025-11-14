"""Session lifecycle endpoints."""

from __future__ import annotations

import chess

from fastapi import APIRouter, HTTPException, Path

from ..board import Board
from .. import engine
from ..schemas import (
    ClockState,
    Explanation,
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

    if payload.uci:
        if board.active_color != player_turn:
            raise HTTPException(status_code=409, detail="It is not the player's turn.")
        legal_moves = board.legal_moves()
        if payload.uci not in legal_moves:
            raise HTTPException(status_code=400, detail="Illegal move.")
        board.apply_uci(payload.uci)
        record.moves.append(payload.uci)
        log_event(
            session_id,
            "player_move",
            {
                "uci": payload.uci,
                "clocks": clocks.model_dump(),
                "move_index": len(record.moves),
            },
        )

        if board.raw.is_checkmate() or board.raw.is_stalemate():
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

    explanation = engine.explain_engine_move(
        board_before_engine_move, engine_move, eval_cp, record.engine_color
    )

    board.apply_uci(engine_move)
    record.moves.append(engine_move)

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
