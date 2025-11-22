"""Session lifecycle endpoints."""

from __future__ import annotations

import chess
import time
from collections import defaultdict
from typing import DefaultDict, List

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response

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
    ReplayResponse,
    ReplayMove,
    OpeningInfo,
)
from ..store import store, SessionRecord
from ..realtime import stream_manager
from ..telemetry import log_event
from ..openings import detect_opening
from ..streaming import stream_update
import chess.pgn

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


def _ordered_move_log(entries: list[dict]) -> list[dict]:
    indexed = []
    for idx, entry in enumerate(entries):
        ply = entry.get("ply", idx + 1)
        indexed.append((ply, idx, entry))
    indexed.sort(key=lambda item: (item[0], item[1]))
    return [entry for _, _, entry in indexed]


def _pgn_result_token(record: SessionRecord) -> str:
    if record.winner == "draw" or record.result == "stalemate":
        return "1/2-1/2"
    if record.winner == "player":
        return "1-0" if record.player_color == "white" else "0-1"
    if record.winner == "engine":
        return "0-1" if record.player_color == "white" else "1-0"
    return "*"


def _build_pgn(record: SessionRecord) -> str:
    game = chess.pgn.Game()
    white_name = "You" if record.player_color == "white" else "Chessica Engine"
    black_name = "Chessica Engine" if record.player_color == "white" else "You"
    game.headers["Event"] = "Chessica"
    game.headers["Site"] = "Chessica"
    game.headers["Date"] = record.created_at.strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    game.headers["Result"] = _pgn_result_token(record)
    initial_fen = record.initial_fen or chess.STARTING_FEN
    if initial_fen != chess.STARTING_FEN:
        game.headers["SetUp"] = "1"
        game.headers["FEN"] = initial_fen
        game.setup(chess.Board(initial_fen))
    board = chess.Board(initial_fen)
    node = game
    uci_moves = [entry.get("uci", "") for entry in _ordered_move_log(record.move_log) if entry.get("uci")]
    for uci in uci_moves:
        try:
            move_obj = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move_obj not in board.legal_moves:
            break
        node = node.add_variation(move_obj)
        board.push(move_obj)
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
    return game.accept(exporter)


@router.post("", response_model=SessionResponse, status_code=201)
def create_session(payload: SessionCreateRequest) -> SessionResponse:
    try:
        record = store.create_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return record.to_response()


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str = Path(..., description="Session identifier")) -> SessionDetail:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    opening = detect_opening(record.moves)
    opening_info = OpeningInfo(name=opening["name"], eco=opening["eco"], ply=len(opening["uci"])) if opening else None
    return record.to_detail().copy(update={"opening": opening_info})


@router.get("/{session_id}/pgn")
def export_pgn(session_id: str = Path(..., description="Session identifier")) -> Response:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    pgn = _build_pgn(record)
    headers = {"Content-Disposition": f'attachment; filename="{session_id}.pgn"'}
    return Response(content=pgn, media_type="application/x-chess-pgn", headers=headers)


@router.get("/{session_id}/replay", response_model=ReplayResponse)
def get_replay(session_id: str = Path(..., description="Session identifier")) -> ReplayResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    moves = _ordered_move_log(record.move_log)
    replay_moves = [
        ReplayMove(
            ply=entry.get("ply", idx + 1),
            side=entry.get("side", "player"),
            san=entry.get("san") or entry.get("uci", ""),
            uci=entry.get("uci", ""),
        )
        for idx, entry in enumerate(moves)
        if entry.get("uci")
    ]
    return ReplayResponse(
        session_id=record.session_id,
        player_color=record.player_color,
        engine_color=record.engine_color,
        status=record.status,
        result=record.result,
        winner=record.winner,
        initial_fen=record.initial_fen or record.fen,
        moves=replay_moves,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/{session_id}/moves", response_model=MoveResponse)
async def make_move(
    payload: MoveRequest,
    session_id: str = Path(..., description="Session identifier"),
) -> MoveResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    if not record.player_id and payload.player_id:
        record.player_id = payload.player_id
    if record.player_id:
        record.player_rating = store.get_player_rating(record.player_id, record.time_control)

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
        # Validate promotion character if present.
        if len(payload.uci) > 4:
            promo = payload.uci[4].lower()
            if promo not in {"q", "r", "b", "n"}:
                raise HTTPException(status_code=400, detail="Invalid promotion piece.")
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
            result, winner, message = _determine_outcome(board, record.player_color)
            record = store.apply_engine_rating(record, winner)
            explanation = Explanation(
                summary=message,
                objective_cost_cp=0,
                alt_best_move="-",
                alt_eval_cp=0,
            )
            game_state = engine.make_game_state(board)
            opening = detect_opening(record.moves)
            opening_info = OpeningInfo(name=opening["name"], eco=opening["eco"], ply=len(opening["uci"])) if opening else None
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
                opening=opening_info,
                player_rating=record.player_rating,
                player_rating_delta=record.player_rating_delta,
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
                    "player_rating": record.player_rating,
                    "player_rating_delta": record.player_rating_delta,
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
    opening = detect_opening(record.moves)
    opening_info = OpeningInfo(name=opening["name"], eco=opening["eco"], ply=len(opening["uci"])) if opening else None

    response = MoveResponse(
        engine_move=engine_move,
        engine_eval_cp=eval_cp,
        exploit_confidence=exploit_confidence,
        opponent_profile=profile,
        explanation=explanation,
        game_state=game_state,
        latest_insight=MoveInsight.model_validate(player_insight_dict) if player_insight_dict else None,
        player_rating=record.player_rating,
        player_rating_delta=record.player_rating_delta,
        opening=opening_info,
    )

    if board.raw.is_checkmate() or board.raw.is_stalemate():
        record.status = "completed"
        result, winner, message = _determine_outcome(board, record.player_color)
        response.result = result
        response.winner = winner
        response.message = message
        record = store.apply_engine_rating(record, winner)
        response.player_rating = record.player_rating
        response.player_rating_delta = record.player_rating_delta
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
                "player_rating": record.player_rating,
                "player_rating_delta": record.player_rating_delta,
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
    opening = detect_opening(record.moves)
    opening_info = OpeningInfo(name=opening["name"], eco=opening["eco"], ply=len(opening["uci"])) if opening else None
    features = engine.extract_position_features(board.raw)
    plans = engine.build_candidate_plans(board.raw, record.difficulty, record.engine_rating)
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
    response = CoachSummaryResponse(
        summary=summary,
        eval_cp=eval_cp,
        position_features=features,
        plans=plans,
        opening=opening_info,
        mode="ideas",
    )
    await stream_update(session_id, {"type": "coach_update", "payload": response.model_dump()})
    return response


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
