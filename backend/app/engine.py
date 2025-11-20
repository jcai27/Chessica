"""Stockfish-backed engine helpers."""

from __future__ import annotations

import atexit
import os
import shlex
import threading
from datetime import datetime, timezone
from pathlib import Path
import re

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
ENGINE_MIN_ELO = 1320


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
                    "UCI_Elo": max(ENGINE_MIN_ELO, min(2850, int(profile["elo"]))),
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
    board: Board,
    move_uci: str,
    eval_cp: int,
    engine_color: str,
    player_feedback: str | None = None,
    difficulty: str | None = None,
    engine_rating: int | None = None,
) -> "Explanation":
    from .schemas import Explanation

    move = chess.Move.from_uci(move_uci)
    snapshot = board.raw
    if move not in snapshot.legal_moves:
        raise ValueError(f"Move {move_uci} is not legal in the given position.")
    analysis_board = snapshot.copy()
    analysis_board.push(move)
    summary = f"Eval {_format_eval_cp(eval_cp)} (centipawns)"
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
                    "UCI_Elo": max(ENGINE_MIN_ELO, min(2850, int(profile["elo"]))),
                }
            )
        except chess.engine.EngineTerminatedError:
            _shutdown_engine()
            engine = _get_engine()
        info = engine.analyse(board.raw, limit, info=chess.engine.INFO_SCORE)
    return _score_to_cp(info.get("score"))


def analyze_position(
    board: chess.Board,
    difficulty: str,
    engine_rating: int,
    multipv: int = 3,
    max_moves: int = 5,
) -> list[dict[str, object]]:
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
                    "UCI_Elo": max(ENGINE_MIN_ELO, min(2850, int(profile["elo"]))),
                }
            )
        except chess.engine.EngineTerminatedError:
            _shutdown_engine()
            engine = _get_engine()
            engine.configure(
                {
                    "Skill Level": max(0, min(20, int(profile.get("skill", 15)))),
                    "UCI_LimitStrength": True,
                    "UCI_Elo": max(ENGINE_MIN_ELO, min(2850, int(profile["elo"]))),
                }
            )
        analysis = engine.analyse(
            board,
            limit,
            multipv=max(1, multipv),
            info=chess.engine.INFO_SCORE | chess.engine.INFO_PV,
        )
    if isinstance(analysis, dict):
        entries = [analysis]
    else:
        entries = analysis or []
    lines: list[dict[str, object]] = []
    for entry in entries:
        pv = entry.get("pv")
        if not pv:
            continue
        temp_board = board.copy(stack=True)
        san_moves: list[str] = []
        for move in pv[:max_moves]:
            try:
                san_moves.append(temp_board.san(move))
            except ValueError:
                san_moves.append(move.uci())
            temp_board.push(move)
        lines.append({"eval_cp": _score_to_cp(entry.get("score")), "san_line": san_moves})
    return lines


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
    verdict_text = {
        "brilliant": "found a brilliant resource that elevates the plan.",
        "great": "chose an ambitious continuation and kept tension high.",
        "good": "followed the strategic blueprint.",
        "sharp": "kept the position dynamic and resourceful.",
        "inaccuracy": "lost a bit of the thread.",
        "mistake": "gave the opponent clear targets.",
        "blunder": "handed over the initiative.",
    }.get(verdict, "made a practical choice.")
    theme_hint = THEME_TIPS.get(_reverse_theme_lookup(themes), "")
    reinforcement = {
        "brilliant": "Keep pressing with the same motif.",
        "great": "Anchor the gain by consolidating your pieces.",
        "good": "Stay alert for tactical ripostes.",
        "sharp": "Balance activity with king safety.",
        "inaccuracy": "Breathe, reinforce your weak squares.",
        "mistake": "Rebuild your coordination and limit further damage.",
        "blunder": "Switch to damage control and hunt counterplay.",
    }.get(verdict, "")
    return " ".join(part for part in (f"{actor} {verdict_text}", theme_hint, reinforcement) if part).strip()


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
) -> list[str]:
    statements = [
        _material_brief(board),
        _center_control_brief(board),
        _space_activity_brief(board, mover_color),
        _king_safety_brief(board),
        _structural_brief(board),
    ]
    if player_feedback:
        statements.insert(0, player_feedback)
    bullets: list[str] = []
    for statement in statements:
        if not statement:
            continue
        parts = _split_sentences(statement)
        bullets.extend(parts)
    return bullets


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


def _center_control_counts(board: chess.Board) -> dict[chess.Color, int]:
    counts = {chess.WHITE: 0, chess.BLACK: 0}
    for square in _EXTENDED_CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece:
            counts[piece.color] += 1
    return counts


def _center_control_brief(board: chess.Board) -> str:
    counts = _center_control_counts(board)
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


def _color_name(color: chess.Color) -> str:
    return "White" if color == chess.WHITE else "Black"


def _coach_mode_summary(
    board: chess.Board,
    eval_cp: int,
    engine_color: str,
    mover_color: chess.Color,
    player_feedback: str | None = None,
    candidate_lines: list[dict[str, object]] | None = None,
) -> str:
    foundation_points = _position_briefing(board, eval_cp, engine_color, mover_color, player_feedback)
    snapshot = _feature_snapshot(board)
    plans = _plan_prompt(board, mover_color)
    sections_ordered: list[tuple[str, list[str]]] = [
        ("Summary", foundation_points),
        ("Strengths", snapshot["strengths"]),
        ("Pressure Points", snapshot["weaknesses"]),
        ("Plans", plans),
    ]

    if candidate_lines:
        formatted = [
            f"{_format_eval_cp(entry.get('eval_cp', 0))}: {' '.join(entry.get('san_line', []))}"
            for entry in candidate_lines
            if entry.get("san_line")
        ]
        sections_ordered.append(("Key Lines", formatted))

    fallback_blocks = [
        _format_section(title, items) for title, items in sections_ordered if items and any(item.strip() for item in items)
    ]
    fallback_text = "\n\n".join(block for block in fallback_blocks if block)
    sections_payload = {
        title.lower().replace(" ", "_"): [item.strip() for item in items if item and item.strip()]
        for title, items in sections_ordered
    }
    return _summarize_with_llm(sections_payload, fallback_text)


def _feature_snapshot(board: chess.Board) -> dict[str, list[str]]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    totals = _material_totals(board)
    diff = totals[chess.WHITE] - totals[chess.BLACK]
    if diff > 120:
        strengths.append("White holds the extra material; aim for trades.")
        weaknesses.append("Black must manufacture counterplay to offset the deficit.")
    elif diff < -120:
        strengths.append("Black owns material leverage and can press quietly.")
        weaknesses.append("White needs active pieces to justify the sacrifice.")

    center_counts = _center_control_counts(board)
    center_diff = center_counts[chess.WHITE] - center_counts[chess.BLACK]
    if center_diff > 1:
        strengths.append("White dominates the central squares.")
        weaknesses.append("Black should look for flank pawn breaks.")
    elif center_diff < -1:
        strengths.append("Black's central grip is restricting White.")
        weaknesses.append("White must undermine the locked center.")

    advanced = _advanced_piece_counts(board)
    space_diff = advanced[chess.WHITE] - advanced[chess.BLACK]
    if space_diff > 1:
        strengths.append("White pieces enjoy extra space to maneuver.")
        weaknesses.append("Black's camp is cramped; swap pieces or hit the base pawns.")
    elif space_diff < -1:
        strengths.append("Black has the more active forces.")
        weaknesses.append("White should neutralize the active pieces before expanding.")

    if _has_bishop_pair(board, chess.WHITE) and not _has_bishop_pair(board, chess.BLACK):
        strengths.append("White's bishop pair loves open diagonals.")
        weaknesses.append("Black should keep the position closed.")
    elif _has_bishop_pair(board, chess.BLACK) and not _has_bishop_pair(board, chess.WHITE):
        strengths.append("Black's bishops can take over light and dark squares.")
        weaknesses.append("White must contest key diagonals.")

    white_passers = _passed_pawns(board, chess.WHITE)
    black_passers = _passed_pawns(board, chess.BLACK)
    if white_passers:
        squares = ", ".join(chess.square_name(sq) for sq in white_passers)
        strengths.append(f"White has a passer on {squares}; support it with rooks.")
    if black_passers:
        squares = ", ".join(chess.square_name(sq) for sq in black_passers)
        strengths.append(f"Black's passed pawn on {squares} will dictate the endgame.")

    if not weaknesses:
        weaknesses.append("Both sides must respect king safety and loose pieces.")
    return {"strengths": strengths, "weaknesses": weaknesses}


def _plan_prompt(board: chess.Board, mover_color: chess.Color) -> list[str]:
    opponent = chess.BLACK if mover_color == chess.WHITE else chess.WHITE
    return [
        _plan_for_color(board, mover_color, opponent),
        _plan_for_color(board, opponent, mover_color),
    ]


def _plan_for_color(board: chess.Board, color: chess.Color, opponent: chess.Color) -> str:
    tips: list[str] = []
    center_counts = _center_control_counts(board)
    center_diff = center_counts[color] - center_counts[opponent]
    if center_diff >= 2:
        tips.append("lean on the central grip and reroute minor pieces onto outposts.")
    elif center_diff <= -2:
        tips.append("challenge the center with timely pawn breaks.")
    advanced = _advanced_piece_counts(board)
    space_diff = advanced[color] - advanced[opponent]
    if space_diff >= 2:
        tips.append("use the space edge to double rooks on the dominant file.")
    elif space_diff <= -2:
        tips.append("trade a few pieces to relieve the cramped camp.")
    if _has_bishop_pair(board, color) and not _has_bishop_pair(board, opponent):
        tips.append("keep lines open so the bishops stay monstrous.")
    passed = _passed_pawns(board, color)
    if passed:
        files = ", ".join(chess.square_name(sq) for sq in passed)
        tips.append(f"nurse the passed pawn on {files} with rook support.")
    if not tips:
        tips.append("improve the least active piece and coordinate with the rooks.")
    return f"{_color_name(color)} plan: {tips[0]}"


def _format_eval_cp(cp: int | float) -> str:
    try:
        value = float(cp) / 100
    except (TypeError, ValueError):
        return "~0.00"
    return f"+{value:.2f}" if value >= 0 else f"{value:.2f}"


def _split_sentences(text: str) -> list[str]:
    segments = re.split(r"(?<=[.!?])\s+", text.strip())
    return [segment.strip() for segment in segments if segment.strip()]


def _summarize_with_llm(sections: dict[str, list[str]], fallback: str) -> str:
    if not settings.coach_llm_url:
        return fallback
    try:
        import httpx
    except ImportError:
        return fallback

    prompt = _compose_llm_prompt(sections)
    payload = {
        "model": settings.coach_llm_model,
        "prompt": prompt,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if settings.coach_llm_api_key:
        headers["Authorization"] = f"Bearer {settings.coach_llm_api_key}"
    try:
        response = httpx.post(
            settings.coach_llm_url,
            json=payload,
            headers=headers,
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return fallback

    summary = (
        data.get("response")
        or data.get("summary")
        or data.get("content")
        or data.get("message")
    )
    if not summary and isinstance(data.get("choices"), list):
        summary = data["choices"][0].get("message", {}).get("content")
    if not summary:
        return fallback
    return summary.strip()


def _format_section(title: str, items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return ""
    bullet_list = "\n".join(f"- {item}" for item in cleaned)
    return f"{title}:\n{bullet_list}"


def _compose_llm_prompt(sections: dict[str, list[str]]) -> str:
    white_points = sections.get("plans", [])
    strengths = sections.get("strengths", [])
    weaknesses = sections.get("pressure_points", [])
    key_lines = sections.get("key_lines", [])
    summary = sections.get("summary", [])
    lines = [
        "Act as a concise chess coach. Write exactly three sentences:",
        "1. What White should aim for overall.",
        "2. What Black should aim for overall.",
        "3. What the current player should do immediately.",
        "Use at most 50 words per sentence.",
        "",
        "Context:",
    ]
    if summary:
        lines.append("Summary cues:")
        lines.extend(f"- {item}" for item in summary)
    if strengths:
        lines.append("Strengths:")
        lines.extend(f"- {item}" for item in strengths)
    if weaknesses:
        lines.append("Pressure points:")
        lines.extend(f"- {item}" for item in weaknesses)
    if white_points:
        lines.append("Plans:")
        lines.extend(f"- {item}" for item in white_points)
    if key_lines:
        lines.append("Key lines:")
        lines.extend(f"- {item}" for item in key_lines)
    lines.append("")
    lines.append("Output:")
    return "\n".join(lines)


def generate_coach_summary(
    board: Board,
    eval_cp: int,
    engine_color: str,
    player_feedback: str | None = None,
    difficulty: str | None = None,
    engine_rating: int | None = None,
) -> str:
    candidate_lines = analyze_position(
        board.raw.copy(stack=True),
        difficulty or "advanced",
        engine_rating or DIFFICULTY_SETTINGS.get("advanced", {}).get("elo", 2000),
    )
    return _coach_mode_summary(
        board.raw.copy(stack=True),
        eval_cp,
        engine_color,
        board.raw.turn,
        player_feedback,
        candidate_lines,
    )


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
