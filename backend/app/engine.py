"""Stockfish-backed engine helpers."""

from __future__ import annotations

import atexit
import os
import shlex
import threading
from datetime import datetime, timezone
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


def explain_engine_move(
    board: Board, move_uci: str, eval_cp: int, engine_color: str, player_feedback: str | None = None
) -> "Explanation":
    from .schemas import Explanation

    move = chess.Move.from_uci(move_uci)
    snapshot = board.raw
    if move not in snapshot.legal_moves:
        raise ValueError(f"Move {move_uci} is not legal in the given position.")
    mover_color = snapshot.turn
    analysis_board = snapshot.copy()
    analysis_board.push(move)
    summary = _position_briefing(analysis_board, eval_cp, engine_color, mover_color, player_feedback)
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

_EXTENDED_CENTER_SQUARES = [
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
]

THEME_LABELS = {
    "king_safety": "king safety",
    "central_control": "central control",
    "material_gain": "material play",
    "piece_activity": "piece activity",
    "king_attack": "king attack",
    "space_gain": "space advantage",
    "passed_pawn": "passed pawn",
    "simplification": "simplification",
}

THEME_TIPS = {
    "king_safety": "Keep building around the king and tie your rooks together.",
    "central_control": "Dominating the center reduces your opponent's counterplay.",
    "material_gain": "With material in hand, exchange into favorable endings.",
    "piece_activity": "Improve the least active piece so everything coordinates.",
    "king_attack": "Keep pieces flowing toward the king and watch for tactical shots.",
    "space_gain": "Fix the space edge by restricting pawn breaks.",
    "passed_pawn": "Put rooks behind the passer and march it confidently.",
    "simplification": "Trade toward a structure your side prefers.",
}


def evaluate_position(board: Board, difficulty: str, engine_rating: int) -> int:
    profile = _difficulty_profile(difficulty, engine_rating)
    think_time = max(0.05, min(settings.engine_move_time_limit, float(profile["move_time"])))
    limit = chess.engine.Limit(time=think_time)
    with ENGINE_LOCK:
        engine = _get_engine()
        try:
            engine.configure(
                {
                    "Skill Level": max(0, min(20, int(profile.get("skill", 15)))),
                    "UCI_LimitStrength": True,
                    "UCI_Elo": max(600, min(2850, int(profile["elo"]))),
                }
            )
        except chess.engine.EngineTerminatedError:
            _shutdown_engine()
            engine = _get_engine()
        info = engine.analyse(board.raw, limit, info=chess.engine.INFO_SCORE)
    return _score_to_cp(info.get("score"))


def build_move_insight(
    before: chess.Board,
    after: chess.Board,
    move: chess.Move,
    mover_color: chess.Color,
    side: str,
    prev_eval_cp: int,
    new_eval_cp: int,
    ply_index: int,
) -> dict[str, object]:
    san = before.san(move)
    delta_cp = new_eval_cp - prev_eval_cp
    if mover_color == chess.BLACK:
        delta_cp = -delta_cp
    verdict = _classify_delta(delta_cp)
    themes = _themes_for_move(before, after, move, mover_color)
    commentary = _compose_commentary(side, verdict, delta_cp, themes)
    return {
        "ply": ply_index,
        "side": side,
        "uci": move.uci(),
        "san": san,
        "eval_cp": new_eval_cp,
        "delta_cp": delta_cp,
        "verdict": verdict,
        "commentary": commentary,
        "themes": themes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _themes_for_move(before: chess.Board, after: chess.Board, move: chess.Move, mover_color: chess.Color) -> list[str]:
    detected = _detect_themes(before, after, move, mover_color)
    labeled = [THEME_LABELS.get(theme, theme.replace("_", " ")) for theme in detected]
    return labeled


def _classify_delta(delta_cp: int) -> str:
    if delta_cp >= 150:
        return "brilliant"
    if delta_cp >= 80:
        return "great"
    if delta_cp >= 30:
        return "good"
    if delta_cp <= -150:
        return "blunder"
    if delta_cp <= -80:
        return "mistake"
    if delta_cp <= -30:
        return "inaccuracy"
    return "sharp"


def _compose_commentary(side: str, verdict: str, delta_cp: int, themes: list[str]) -> str:
    actor = "You" if side == "player" else "The engine"
    swing = f"{abs(delta_cp) / 100:.2f}"
    if verdict in {"brilliant", "great"}:
        prefix = f"{actor} found a {verdict} idea"
    elif verdict in {"good", "sharp"}:
        prefix = f"{actor} keeps the plan healthy"
    elif verdict == "inaccuracy":
        prefix = f"{actor} slipped slightly"
    elif verdict == "mistake":
        prefix = f"{actor} let the evaluation drift"
    else:
        prefix = f"{actor} blundered"
    theme_hint = THEME_TIPS.get(_reverse_theme_lookup(themes), "")
    impact = f"shifting the eval by {swing} pawns."
    return " ".join(part for part in (prefix + ",", theme_hint or "", impact) if part).strip()


def _reverse_theme_lookup(themes: list[str]) -> str:
    reverse = {value: key for key, value in THEME_LABELS.items()}
    for theme in themes:
        key = reverse.get(theme)
        if key:
            return key
    return ""


def _position_briefing(
    board: chess.Board,
    eval_cp: int,
    engine_color: str,
    mover_color: chess.Color,
    player_feedback: str | None = None,
) -> str:
    statements = [
        _material_brief(board),
        _center_control_brief(board),
        _space_activity_brief(board, mover_color),
        _king_safety_brief(board),
        _structural_brief(board),
        _score_sentence(eval_cp, engine_color),
    ]
    if player_feedback:
        statements.insert(0, player_feedback)
    return " ".join(part for part in statements if part).strip()


def _material_brief(board: chess.Board) -> str:
    totals = _material_totals(board)
    diff = totals[chess.WHITE] - totals[chess.BLACK]
    if abs(diff) < 80:
        return "Material is level, so plans revolve around piece activity and pawn structure."
    pawns = abs(diff) / 100
    formatted = f"{pawns:.1f}".rstrip('0').rstrip('.')
    leader = "White" if diff > 0 else "Black"
    return f"{leader} holds roughly a {formatted}-pawn material edge, letting that side dictate the trades."


def _material_totals(board: chess.Board) -> dict[chess.Color, int]:
    totals = {chess.WHITE: 0, chess.BLACK: 0}
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        totals[piece.color] += _PIECE_VALUES.get(piece.piece_type, 0)
    return totals


def _center_control_brief(board: chess.Board) -> str:
    counts = {chess.WHITE: 0, chess.BLACK: 0}
    for square in _EXTENDED_CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece:
            counts[piece.color] += 1
    diff = counts[chess.WHITE] - counts[chess.BLACK]
    if diff > 1:
        return "White pieces dominate the central squares, limiting counterplay."
    if diff < -1:
        return "Black has seized the central dark squares, so White must look for flanks."
    return "Central control is shared, making timing and move order critical."


def _space_activity_brief(board: chess.Board, mover_color: chess.Color) -> str:
    advanced = _advanced_piece_counts(board)
    opponent = chess.BLACK if mover_color == chess.WHITE else chess.WHITE
    difference = advanced[mover_color] - advanced[opponent]
    mover_name = _color_name(mover_color)
    if difference >= 2:
        return f"{mover_name} pieces are planted deep in enemy territory, so keep pressing the space advantage."
    if difference <= -2:
        opponent_name = _color_name(opponent)
        return f"{opponent_name} has the more active army right now; tighten your coordination before counterattacking."
    return f"Piece activity is balanced, so {mover_name} should improve the worst-placed piece before launching tactics."


def _advanced_piece_counts(board: chess.Board) -> dict[chess.Color, int]:
    counts = {chess.WHITE: 0, chess.BLACK: 0}
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        rank = chess.square_rank(square)
        if piece.color == chess.WHITE and rank >= 4:
            counts[chess.WHITE] += 1
        elif piece.color == chess.BLACK and rank <= 3:
            counts[chess.BLACK] += 1
    return counts


def _king_safety_brief(board: chess.Board) -> str:
    white = _king_safety_status(board, chess.WHITE)
    black = _king_safety_status(board, chess.BLACK)
    return f"{white} {black}".strip()


def _king_safety_status(board: chess.Board, color: chess.Color) -> str:
    king_square = board.king(color)
    if king_square is None:
        return ""
    name = _color_name(color)
    rank = chess.square_rank(king_square)
    file = chess.square_file(king_square)
    if color == chess.WHITE:
        if rank == 0 and file >= 5:
            return f"{name}'s king is tucked on the kingside, so the rook can join quickly."
        if rank == 0 and file <= 2:
            return f"{name}'s king has gone queenside; activate rooks toward the center."
    else:
        if rank == 7 and file >= 5:
            return f"{name}'s king mirrors that safety on g8, making direct attacks harder."
        if rank == 7 and file <= 2:
            return f"{name} committed to a long castle, so watch the a- and b-files."
    return f"{name}'s king still lingers in the center, so development with tempo is vital."


def _structural_brief(board: chess.Board) -> str:
    blurbs: list[str] = []
    if _has_bishop_pair(board, chess.WHITE) and not _has_bishop_pair(board, chess.BLACK):
        blurbs.append("White enjoys the bishop pair, which favors open play.")
    elif _has_bishop_pair(board, chess.BLACK) and not _has_bishop_pair(board, chess.WHITE):
        blurbs.append("Black keeps the bishops, so look to steer the game open.")
    white_passed = _passed_pawns(board, chess.WHITE)
    black_passed = _passed_pawns(board, chess.BLACK)
    if white_passed and not black_passed:
        files = ", ".join(chess.square_name(sq) for sq in white_passed)
        blurbs.append(f"White owns a passed pawn on {files}; shepherd it forward with rook support.")
    elif black_passed and not white_passed:
        files = ", ".join(chess.square_name(sq) for sq in black_passed)
        blurbs.append(f"Black's passed pawn on {files} is the long-term trump to watch.")
    if not blurbs:
        return ""
    return " ".join(blurbs)


def _has_bishop_pair(board: chess.Board, color: chess.Color) -> bool:
    return len(board.pieces(chess.BISHOP, color)) >= 2


def _passed_pawns(board: chess.Board, color: chess.Color) -> list[chess.Square]:
    squares: list[chess.Square] = []
    for square in board.pieces(chess.PAWN, color):
        if _pawn_is_passed(board, square, color):
            squares.append(square)
    return squares


def _pawn_is_passed(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    enemy = chess.BLACK if color == chess.WHITE else chess.WHITE
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    direction = 1 if color == chess.WHITE else -1
    next_rank = rank_idx + direction
    while 0 <= next_rank < 8:
        for adj_file in (file_idx - 1, file_idx, file_idx + 1):
            if not (0 <= adj_file < 8):
                continue
            target_square = chess.square(adj_file, next_rank)
            target_piece = board.piece_at(target_square)
            if target_piece and target_piece.color == enemy and target_piece.piece_type == chess.PAWN:
                return False
        next_rank += direction
    return True


def _score_sentence(eval_cp: int, engine_color: str) -> str:
    perspective = eval_cp if engine_color == "white" else -eval_cp
    if abs(perspective) < 40:
        return "Engine evaluation keeps the position roughly level."
    pawns = abs(perspective) / 100
    formatted = f"{pawns:.2f}".rstrip('0').rstrip('.')
    if perspective > 0:
        return f"The engine sees itself ahead by about {formatted} pawns."
    return f"The engine still trails by roughly {formatted} pawns."


def _color_name(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


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


def _is_strong_center(square: chess.Square) -> bool:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    return 2 <= file_idx <= 5 and 2 <= rank_idx <= 5


def _pushes_space(move: chess.Move, mover_color: chess.Color) -> bool:
    rank = chess.square_rank(move.to_square)
    return rank >= 4 if mover_color == chess.WHITE else rank <= 3


def _advanced_piece_placement(square: chess.Square, mover_color: chess.Color) -> bool:
    rank = chess.square_rank(square)
    return rank >= 4 if mover_color == chess.WHITE else rank <= 3


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
    return _pawn_is_passed(after, move.to_square, mover_color)


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
