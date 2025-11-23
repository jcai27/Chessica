"""Exploit-aware search implementation."""

from __future__ import annotations

import chess
import chess.engine
import math
from typing import List, Tuple, Optional

from .engine import _get_engine, _score_to_cp, ENGINE_LOCK, ENGINE_MIN_ELO
from .opponent_model import ProfileService
from .database import SessionLocal

class ExploitSearch:
    def __init__(self, profile_service: ProfileService):
        self.profile_service = profile_service

    def search(
        self, 
        board: chess.Board, 
        user_id: str, 
        time_limit: float = 1.0, 
        depth: int = 10
    ) -> Tuple[str, int, float]:
        """
        Finds a move that maximizes: ObjectiveScore + (ExploitBonus * ErrorProb)
        Returns: (best_move_uci, eval_cp, exploit_confidence)
        """
        
        # 1. Get candidate moves from Stockfish (MultiPV)
        candidates = self._get_candidates(board, time_limit, depth)
        
        if not candidates:
            raise ValueError("No moves found")

        best_move = candidates[0]["move"]
        best_score = candidates[0]["score"]
        best_composite_score = -float("inf")
        exploit_confidence = 0.0

        # 2. Evaluate each candidate for exploit potential
        for cand in candidates:
            move = cand["move"]
            score = cand["score"]
            
            # If the move is objectively losing compared to best, skip unless we are desperate
            # (Don't play a blunder just to trick the opponent)
            if score < best_score - 150: 
                continue

            # Predict opponent error probability after this move
            # We simulate the opponent's turn. 
            # The "error" is them NOT finding the refutation.
            board.push(chess.Move.from_uci(move))
            error_prob = self.profile_service.predict_error_probability(user_id, board.fen(), move)
            board.pop()
            
            # Exploit Bonus: If they err, we gain. 
            # Simple model: ExpectedValue = (1-P_error)*Score + P_error*(Score + Benefit)
            # Here we just add a bonus to the score for ranking.
            exploit_bonus = error_prob * 200 # 200cp bonus for high error probability
            
            composite_score = score + exploit_bonus
            
            if composite_score > best_composite_score:
                best_composite_score = composite_score
                best_move = move
                exploit_confidence = error_prob

        return best_move, best_score, exploit_confidence

    def _get_candidates(self, board: chess.Board, time_limit: float, depth: int) -> List[dict]:
        """Get top K moves with their objective scores."""
        limit = chess.engine.Limit(time=time_limit, depth=depth)
        with ENGINE_LOCK:
            engine = _get_engine()
            # Ensure engine is at full strength for analysis
            engine.configure({"Skill Level": 20, "UCI_LimitStrength": False})
            
            result = engine.analyse(
                board, 
                limit, 
                multipv=5, # Look at top 5 moves
                info=chess.engine.INFO_SCORE
            )
            
        candidates = []
        for info in result:
            if "pv" not in info: continue
            move = info["pv"][0].uci()
            score = _score_to_cp(info["score"])
            candidates.append({"move": move, "score": score})
            
        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates
