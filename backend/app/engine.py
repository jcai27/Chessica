"""Lightweight heuristic engine with alpha-beta search."""

from __future__ import annotations

import math
from random import choice, random

import chess

from .board import Board
from .schemas import Explanation, GameState, OpponentProfile

SAMPLE_MOTIFS = ["forks", "back_rank", "time_trouble", "endgame"]
CHECKMATE_SCORE = 100_000
CHECK_BONUS = 50
MOBILITY_WEIGHT = 5
KING_SHIELD_BONUS = 15
QUIESCENCE_MAX = 4

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PAWN_TABLE = [
     0,  5,  5, -10, -10,  5,  5,  0,
     0, 10, -5,   0,   0, -5, 10,  0,
     0, 10, 10,  20,  20, 10, 10,  0,
     5, 15, 15,  25,  25, 15, 15,  5,
    10, 20, 20,  30,  30, 20, 20, 10,
    15, 25, 25,  35,  35, 25, 25, 15,
    20, 30, 30,  40,  40, 30, 30, 20,
     0,  0,  0,   0,   0,  0,  0,  0,
]

KNIGHT_TABLE = [
   -50, -30, -10, -10, -10, -10, -30, -50,
   -30,  10,  15,  20,  20,  15,  10, -30,
   -10,  15,  25,  30,  30,  25,  15, -10,
   -10,  20,  30,  35,  35,  30,  20, -10,
   -10,  20,  30,  35,  35,  30,  20, -10,
   -10,  15,  25,  30,  30,  25,  15, -10,
   -30,  10,  15,  20,  20,  15,  10, -30,
   -50, -30, -10, -10, -10, -10, -30, -50,
]

BISHOP_TABLE = [
   -20, -10, -10, -10, -10, -10, -10, -20,
   -10,  10,  10,  10,  10,  10,  10, -10,
   -10,  10,  15,  15,  15,  15,  10, -10,
   -10,  10,  15,  20,  20,  15,  10, -10,
   -10,  10,  15,  20,  20,  15,  10, -10,
   -10,  10,  15,  15,  15,  15,  10, -10,
   -10,  15,  10,  10,  10,  10,  15, -10,
   -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_TABLE = [
     0,   0,   5,  10,  10,   5,   0,   0,
    10,  20,  20,  20,  20,  20,  20,  10,
     5,  10,  10,  10,  10,  10,  10,   5,
     0,   0,   5,  10,  10,   5,   0,   0,
     0,   0,   5,  10,  10,   5,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    10,  20,  20,  20,  20,  20,  20,  10,
     0,   0,   5,  10,  10,   5,   0,   0,
]

QUEEN_TABLE = [
   -20, -10, -10,  -5,  -5, -10, -10, -20,
   -10,   0,   5,   0,   0,   5,   0, -10,
   -10,   5,   5,   5,   5,   5,   5, -10,
    -5,   0,   5,   5,   5,   5,   0,  -5,
     0,   0,   5,   5,   5,   5,   0,  -5,
   -10,   5,   5,   5,   5,   5,   5, -10,
   -10,   0,   5,   0,   0,   5,   0, -10,
   -20, -10, -10,  -5,  -5, -10, -10, -20,
]

KING_TABLE = [
    20,  30,  10,   0,   0,  10,  30,  20,
    20,  20,   0,   0,   0,   0,  20,  20,
   -10, -20, -20, -20, -20, -20, -20, -10,
   -20, -30, -30, -40, -40, -30, -30, -20,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
   -30, -40, -40, -50, -50, -40, -40, -30,
]

PIECE_SQUARE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}


def pick_engine_move(board: Board, color: str, depth: int) -> tuple[str, int]:
    if board.active_color != color:
        raise ValueError("Engine turn mismatch")

    depth = max(1, min(depth, 5))
    root = board.raw.copy(stack=True)
    engine_is_white = color == "w"

    alpha = -math.inf
    beta = math.inf
    best_score = -math.inf
    best_move = None

    for move in order_moves(root):
        root.push(move)
        score = -negamax(root, depth - 1, -beta, -alpha, engine_is_white)
        root.pop()
        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, score)

    if best_move is None:
        raise ValueError("No legal moves available for engine.")

    eval_cp = CHECKMATE_SCORE if math.isinf(best_score) else int(best_score)
    return best_move.uci(), eval_cp


def negamax(board: chess.Board, depth: int, alpha: float, beta: float, engine_is_white: bool) -> float:
    if depth == 0 or board.is_game_over():
        return quiescence(board, alpha, beta, engine_is_white)

    value = -math.inf
    for move in order_moves(board):
        board.push(move)
        score = -negamax(board, depth - 1, -beta, -alpha, engine_is_white)
        board.pop()
        value = max(value, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return value


def quiescence(board: chess.Board, alpha: float, beta: float, engine_is_white: bool, depth: int = 0) -> float:
    stand_pat = evaluate_position(board, engine_is_white)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    if depth >= QUIESCENCE_MAX:
        return stand_pat

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        board.push(move)
        score = -quiescence(board, -beta, -alpha, engine_is_white, depth + 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def order_moves(board: chess.Board) -> list[chess.Move]:
    def move_score(move: chess.Move) -> int:
        score = 0
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if captured:
                score += 10 * PIECE_VALUES[captured.piece_type]
            if attacker:
                score -= PIECE_VALUES[attacker.piece_type]
        if board.gives_check(move):
            score += CHECK_BONUS
        if move.promotion:
            score += PIECE_VALUES.get(move.promotion, 0)
        return score

    moves = list(board.legal_moves)
    moves.sort(key=move_score, reverse=True)
    return moves


def evaluate_position(board: chess.Board, engine_is_white: bool) -> float:
    if board.is_checkmate():
        loser_is_engine = board.turn == (chess.WHITE if engine_is_white else chess.BLACK)
        return -CHECKMATE_SCORE if loser_is_engine else CHECKMATE_SCORE
    if board.is_stalemate():
        return 0

    score = 0.0
    for square, piece in board.piece_map().items():
        piece_value = PIECE_VALUES[piece.piece_type]
        pst = piece_square_value(piece, square)
        contribution = piece_value + pst
        score += contribution if piece.color == chess.WHITE else -contribution

    if not engine_is_white:
        score = -score

    mobility_diff = mobility(board, engine_is_white) - mobility(board, not engine_is_white)
    score += MOBILITY_WEIGHT * mobility_diff
    score += king_safety(board, engine_is_white)
    score += random() * 2
    return score


def mobility(board: chess.Board, color_is_white: bool) -> int:
    clone = board.copy(stack=False)
    clone.turn = chess.WHITE if color_is_white else chess.BLACK
    return clone.legal_moves.count()


def king_safety(board: chess.Board, engine_is_white: bool) -> float:
    king_square = board.king(chess.WHITE if engine_is_white else chess.BLACK)
    if king_square is None:
        return 0
    shield = 0
    king_rank = chess.square_rank(king_square)
    direction = -1 if engine_is_white else 1
    for file_delta in (-1, 0, 1):
        file_index = chess.square_file(king_square) + file_delta
        rank_index = king_rank + direction
        if 0 <= file_index < 8 and 0 <= rank_index < 8:
            sq = chess.square(file_index, rank_index)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN and piece.color == (chess.WHITE if engine_is_white else chess.BLACK):
                shield += KING_SHIELD_BONUS
    return shield


def piece_square_value(piece: chess.Piece, square: chess.Square) -> int:
    table = PIECE_SQUARE_TABLES.get(piece.piece_type)
    if not table:
        return 0
    index = square if piece.color == chess.WHITE else chess.square_mirror(square)
    return table[index]


def mock_exploit_confidence() -> float:
    return round(0.4 + random() * 0.5, 2)


def mock_opponent_profile() -> OpponentProfile:
    motif_scores = {motif: round(random(), 2) for motif in SAMPLE_MOTIFS[:3]}
    return OpponentProfile(
        style={"tactical": round(random(), 2), "risk": round(random(), 2)},  # type: ignore[arg-type]
        motif_risk=motif_scores,
    )


def mock_explanation(move: str) -> Explanation:
    return Explanation(
        summary=f"Steers toward {choice(SAMPLE_MOTIFS)} patterns aligned with observed weaknesses.",
        objective_cost_cp=choice([5, 12, 18]),
        alt_best_move="g8f6",
        alt_eval_cp=choice([25, 40, 55]),
    )


def make_game_state(board: Board) -> GameState:
    return GameState(
        fen=board.to_fen(),
        move_number=board.fullmove,
        turn="white" if board.active_color == "w" else "black",
    )
