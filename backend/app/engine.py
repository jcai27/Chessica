"""Stockfish-backed engine helpers."""

from __future__ import annotations

import atexit
import os
import shlex
import threading
from pathlib import Path

import chess
import chess.engine

from .config import settings
from .board import Board

ENGINE_LOCK = threading.Lock()
ENGINE: chess.engine.SimpleEngine | None = None

DIFFICULTY_SETTINGS: dict[str, dict[str, float | int]] = {
    "beginner": {"skill": 1, "elo": 900, "move_time": 0.2},
    "intermediate": {"skill": 5, "elo": 1200, "move_time": 0.25},
    "advanced": {"skill": 10, "elo": 1600, "move_time": 0.35},
    "expert": {"skill": 15, "elo": 2000, "move_time": 0.45},
    "grandmaster": {"skill": 20, "elo": 2400, "move_time": 0.6},
    "custom": {"skill": 15, "elo": 2000, "move_time": 0.4},
}


def _engine_cmd() -> list[str]:
    path = Path(settings.stockfish_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Stockfish executable not found at {path}.")
    cmd = str(path)
    if os.name == "nt":
        return [cmd]
    return shlex.split(cmd)


def _shutdown_engine() -> None:
    global ENGINE
    if ENGINE is not None:
        try:
            ENGINE.quit()
        finally:
            ENGINE = None


def _get_engine() -> chess.engine.SimpleEngine:
    global ENGINE
    if ENGINE is None:
        ENGINE = chess.engine.SimpleEngine.popen_uci(_engine_cmd())
        atexit.register(_shutdown_engine)
    return ENGINE


def _difficulty_profile(difficulty: str, engine_rating: int) -> dict[str, float | int]:
    if difficulty in DIFFICULTY_SETTINGS:
        profile = DIFFICULTY_SETTINGS[difficulty].copy()
    else:
        profile = DIFFICULTY_SETTINGS["custom"].copy()
    profile["elo"] = engine_rating
    move_time = float(profile.get("move_time", settings.engine_move_time_limit))
    profile["move_time"] = min(settings.engine_move_time_limit, move_time)
    return profile


def _score_to_cp(score: chess.engine.PovScore | None) -> int:
    if score is None:
        return 0
    pov = score.white()
    if pov.is_mate():
        mate_score = CHECKMATE_CP if pov.mate() and pov.mate() > 0 else -CHECKMATE_CP
        return mate_score
    return pov.score() or 0


CHECKMATE_CP = 10000


def pick_engine_move(board: Board, difficulty: str, engine_rating: int) -> tuple[str, int]:
    if board.raw.is_game_over():
        raise ValueError("Game already over.")

    profile = _difficulty_profile(difficulty, engine_rating)
    think_time = max(0.05, min(settings.engine_move_time_limit, float(profile["move_time"])))
    skill = int(profile.get("skill", 15))
    limit = chess.engine.Limit(time=think_time)

    with ENGINE_LOCK:
        engine = _get_engine()
        try:
            engine.configure(
                {
                    "Skill Level": max(0, min(20, skill)),
                    "UCI_LimitStrength": True,
                    "UCI_Elo": max(600, min(2850, int(profile["elo"]))),
                }
            )
        except chess.engine.EngineTerminatedError:
            _shutdown_engine()
            engine = _get_engine()
        result = engine.play(board.raw, limit, info=chess.engine.INFO_SCORE)
        if result.move is None:
            raise ValueError("Engine failed to return a move.")
        eval_cp = _score_to_cp(result.info.get("score"))
        return result.move.uci(), eval_cp


def make_game_state(board: Board) -> "GameState":
    from .schemas import GameState

    return GameState(
        fen=board.to_fen(),
        move_number=board.fullmove,
        turn="white" if board.active_color == "w" else "black",
    )


def mock_opponent_profile() -> "OpponentProfile":
    from random import random

    from .schemas import OpponentProfile

    return OpponentProfile(
        style={"tactical": round(random(), 2), "risk": round(random(), 2)},  # type: ignore[arg-type]
        motif_risk={"forks": round(random(), 2), "back_rank": round(random(), 2)},
    )


def mock_exploit_confidence() -> float:
    from random import random

    return round(0.4 + random() * 0.5, 2)


def explain_engine_move(board: Board, move_uci: str, eval_cp: int, engine_color: str) -> "Explanation":
    from .schemas import Explanation

    move = chess.Move.from_uci(move_uci)
    snapshot = board.raw
    if move not in snapshot.legal_moves:
        raise ValueError(f"Move {move_uci} is not legal in the given position.")
    mover_color = snapshot.turn
    analysis_board = snapshot.copy()
    analysis_board.push(move)
    summary = _summarize_move(snapshot, analysis_board, move, mover_color, engine_color, eval_cp)
    return Explanation(
        summary=summary,
        objective_cost_cp=0,
        alt_best_move="-",
        alt_eval_cp=eval_cp,
    )


_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def _summarize_move(
    before: chess.Board,
    after: chess.Board,
    move: chess.Move,
    mover_color: chess.Color,
    engine_color: str,
    eval_cp: int,
) -> str:
    parts: list[str] = []
    parts.append(_primary_action_sentence(before, after, move, mover_color))
    theme = _theme_sentence(before, after, move, mover_color)
    if theme:
        parts.append(theme)
    parts.extend(_follow_up_sentences(after, move, mover_color))
    score_blurb = _score_sentence(eval_cp, engine_color)
    if score_blurb:
        parts.append(score_blurb)
    return " ".join(part for part in parts if part).strip()


def _primary_action_sentence(
    before: chess.Board, after: chess.Board, move: chess.Move, mover_color: chess.Color
) -> str:
    piece_type = before.piece_type_at(move.from_square)
    piece_name = chess.piece_name(piece_type or chess.PAWN)
    destination = chess.square_name(move.to_square)
    if before.is_castling(move):
        side = "kingside" if chess.square_file(move.to_square) > chess.square_file(move.from_square) else "queenside"
        return f"Castles {side} to tuck the king away and mobilize the rook."
    if move.promotion:
        promo_name = chess.piece_name(move.promotion)
        return f"Promotes the pawn on {destination} into a {promo_name}, adding a fresh attacker."
    if before.is_capture(move):
        target_square = move.to_square
        target_piece = before.piece_type_at(move.to_square)
        if target_piece is None and before.is_en_passant(move):
            offset = -8 if mover_color == chess.WHITE else 8
            target_square = move.to_square + offset
            target_piece = chess.PAWN
        captured = chess.piece_name(target_piece or chess.PAWN)
        return f"{piece_name.title()} captures your {captured} on {chess.square_name(target_square)}."
    if piece_type == chess.PAWN:
        text = f"Advances the pawn to {destination}"
    elif piece_type in (chess.KNIGHT, chess.BISHOP, chess.QUEEN) and _is_strong_center(move.to_square):
        text = f"Centralizes the {piece_name} on {destination}"
    else:
        text = f"Repositions the {piece_name} to {destination}"
    if piece_type == chess.ROOK and _file_is_open(after, move.to_square):
        text += " to seize the open file"
    return f"{text}."


def _follow_up_sentences(after: chess.Board, move: chess.Move, mover_color: chess.Color) -> list[str]:
    details: list[str] = []
    if after.is_checkmate():
        details.append("The move delivers checkmate.")
        return details
    if after.is_check():
        details.append("It also checks your king.")
    threat = _threat_sentence(after, move, mover_color)
    if threat:
        details.append(threat)
    if _creates_passed_pawn(after, move, mover_color):
        details.append("The pawn is now passed and can become a long-term asset.")
    if _aligns_with_king(after, move, mover_color):
        details.append("The move lines up directly with your king, increasing pressure.")
    return details


def _threat_sentence(after: chess.Board, move: chess.Move, mover_color: chess.Color) -> str:
    targets: list[tuple[int, chess.Piece, int]] = []
    for square in after.attacks(move.to_square):
        piece = after.piece_at(square)
        if piece and piece.color != mover_color:
            value = _PIECE_VALUES.get(piece.piece_type, 0)
            targets.append((value, piece, square))
    if not targets:
        return ""
    _, piece, square = max(targets, key=lambda item: item[0])
    name = chess.piece_name(piece.piece_type)
    square_name = chess.square_name(square)
    if piece.piece_type == chess.KING:
        return "It forces your king to stay alert to new threats."
    return f"It now threatens your {name} on {square_name}."


def _score_sentence(eval_cp: int, engine_color: str) -> str:
    perspective = eval_cp if engine_color == "white" else -eval_cp
    if abs(perspective) < 40:
        return "Engine evaluation keeps the position roughly level."
    pawns = abs(perspective) / 100
    formatted = f"{pawns:.2f}".rstrip("0").rstrip(".")
    if perspective > 0:
        return f"The engine sees itself ahead by about {formatted} pawns."
    return f"The engine still trails by roughly {formatted} pawns."


def _is_strong_center(square: chess.Square) -> bool:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    return 2 <= file_idx <= 5 and 2 <= rank_idx <= 5


def _file_is_open(board: chess.Board, square: chess.Square) -> bool:
    file_idx = chess.square_file(square)
    for rank in range(8):
        sq = chess.square(file_idx, rank)
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN:
            return False
    return True


def _creates_passed_pawn(after: chess.Board, move: chess.Move, mover_color: chess.Color) -> bool:
    piece = after.piece_at(move.to_square)
    if not piece or piece.piece_type != chess.PAWN:
        return False
    enemy = chess.BLACK if mover_color == chess.WHITE else chess.WHITE
    file_idx = chess.square_file(move.to_square)
    rank_idx = chess.square_rank(move.to_square)
    direction = 1 if mover_color == chess.WHITE else -1
    next_rank = rank_idx + direction
    while 0 <= next_rank < 8:
        for adj_file in (file_idx - 1, file_idx, file_idx + 1):
            if not (0 <= adj_file < 8):
                continue
            sq = chess.square(adj_file, next_rank)
            target = after.piece_at(sq)
            if target and target.color == enemy and target.piece_type == chess.PAWN:
                return False
        next_rank += direction
    return True


def _aligns_with_king(after: chess.Board, move: chess.Move, mover_color: chess.Color) -> bool:
    slider = after.piece_at(move.to_square)
    if not slider or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    enemy_king = after.king(chess.BLACK if mover_color == chess.WHITE else chess.WHITE)
    if enemy_king is None:
        return False
    between_mask = chess.between(enemy_king, move.to_square)
    if between_mask == 0:
        return False
    for sq in chess.SquareSet(between_mask):
        if after.piece_at(sq):
            return False
    return True


def _theme_sentence(
    before: chess.Board,
    after: chess.Board,
    move: chess.Move,
    mover_color: chess.Color,
) -> str:
    themes = _detect_themes(before, after, move, mover_color)
    if not themes:
        return ""
    THEME_DESCRIPTIONS = {
        "king_safety": "Prioritizes king safety so the attack can continue from a stable base.",
        "central_control": "Strengthens central control to choke your counterplay.",
        "material_gain": "Keeps the plan pragmatic by banking material.",
        "piece_activity": "Builds piece activity to improve future coordination.",
        "king_attack": "Feeds into the broader attack on your king.",
        "space_gain": "Claims extra space to squeeze your position.",
        "passed_pawn": "Commits to a long-term plan of advancing the passed pawn.",
        "simplification": "Steers toward a simplified position that favors the engine's structure.",
    }
    ordered = [desc for key, desc in THEME_DESCRIPTIONS.items() if key in themes]
    return ordered[0] if ordered else ""


def _detect_themes(
    before: chess.Board,
    after: chess.Board,
    move: chess.Move,
    mover_color: chess.Color,
) -> set[str]:
    themes: set[str] = set()
    piece_type = before.piece_type_at(move.from_square) or chess.PAWN
    destination = move.to_square
    if before.is_castling(move) or piece_type == chess.KING:
        themes.add("king_safety")
    if piece_type == chess.PAWN and _is_center_square(destination):
        themes.add("central_control")
    if piece_type in (chess.KNIGHT, chess.BISHOP, chess.QUEEN) and _is_strong_center(destination):
        themes.add("central_control")
        themes.add("piece_activity")
    if piece_type == chess.ROOK and _file_is_open(after, destination):
        themes.add("piece_activity")
    if before.is_capture(move):
        themes.add("material_gain")
        if before.piece_type_at(move.from_square) == before.piece_type_at(move.to_square):
            themes.add("simplification")
    if after.is_check() or _aligns_with_king(after, move, mover_color):
        themes.add("king_attack")
    if _creates_passed_pawn(after, move, mover_color):
        themes.add("passed_pawn")
    if piece_type == chess.PAWN and _pushes_space(move, mover_color):
        themes.add("space_gain")
    if piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN) and _advanced_piece_placement(
        destination, mover_color
    ):
        themes.add("piece_activity")
    return themes


def _is_center_square(square: chess.Square) -> bool:
    return chess.square_file(square) in (2, 3, 4, 5) and chess.square_rank(square) in (2, 3, 4, 5)


def _pushes_space(move: chess.Move, mover_color: chess.Color) -> bool:
    rank = chess.square_rank(move.to_square)
    return rank >= 4 if mover_color == chess.WHITE else rank <= 3


def _advanced_piece_placement(square: chess.Square, mover_color: chess.Color) -> bool:
    rank = chess.square_rank(square)
    return rank >= 4 if mover_color == chess.WHITE else rank <= 3
