import pytest
import chess
from app.engine import (
    _difficulty_profile,
    _score_to_cp,
    _material_phase,
    _material_diff,
    DIFFICULTY_SETTINGS,
    CHECKMATE_CP
)

def test_difficulty_profile_defaults():
    profile = _difficulty_profile("beginner", 1000)
    assert profile["skill"] == 1
    assert profile["elo"] == 1000
    assert profile["move_time"] == 0.2

def test_difficulty_profile_custom():
    profile = _difficulty_profile("custom", 1800)
    assert profile["elo"] == 1800
    # Should fall back to custom defaults for other fields if not specified in args (though args only take rating)
    assert profile["skill"] == 15 

def test_score_to_cp_none():
    assert _score_to_cp(None) == 0

def test_score_to_cp_mate():
    # Mate in 1 for white
    score = chess.engine.PovScore(chess.engine.Mate(1), chess.WHITE)
    assert _score_to_cp(score) == CHECKMATE_CP
    
    # Mate in 1 for black (from white's POV this is negative)
    score = chess.engine.PovScore(chess.engine.Mate(1), chess.BLACK)
    assert _score_to_cp(score) == -CHECKMATE_CP

def test_material_phase():
    board = chess.Board()
    assert _material_phase(board) == "opening"
    
    # Remove queens
    board.remove_piece_at(chess.D1)
    board.remove_piece_at(chess.D8)
    assert _material_phase(board) == "middlegame" # 78 - 18 = 60 <= 65

def test_material_diff():
    board = chess.Board()
    assert _material_diff(board) == 0
    
    # Remove white pawn
    board.remove_piece_at(chess.E2)
    assert _material_diff(board) == -100
