"""Opponent modeling service."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import chess
from sqlalchemy.orm import Session

from .models import OpponentProfileModel, SessionModel
from .database import SessionLocal

class ProfileService:
    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, user_id: str) -> dict:
        """Retrieve or initialize a user's profile."""
        profile = self.db.get(OpponentProfileModel, user_id)
        if not profile:
            profile = OpponentProfileModel(
                user_id=user_id,
                style_vector={"tactical": 0.5, "risk": 0.5},
                motif_risks={}
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        
        return {
            "style": profile.style_vector,
            "motif_risks": profile.motif_risks,
            "games_played": profile.games_played
        }

    def update_profile(self, user_id: str, session: SessionModel) -> None:
        """Analyze a completed session to update the user's profile."""
        profile = self.db.get(OpponentProfileModel, user_id)
        if not profile:
            self.get_profile(user_id) # Ensure exists
            profile = self.db.get(OpponentProfileModel, user_id)

        # Simple heuristic updates based on game outcome and length
        # In a real system, this would replay the game with an engine to find missed tactics.
        
        style = dict(profile.style_vector)
        risks = dict(profile.motif_risks)
        
        # Example heuristic: Short losses imply tactical fragility
        moves = len(session.moves) if session.moves else 0
        if session.winner == "engine" and moves < 40:
            style["tactical"] = max(0.1, style.get("tactical", 0.5) - 0.05)
            risks["early_blunder"] = min(1.0, risks.get("early_blunder", 0.0) + 0.1)
        
        # Example heuristic: Long games imply positional solidity
        if moves > 80:
            style["risk"] = max(0.1, style.get("risk", 0.5) - 0.05)

        profile.style_vector = style
        profile.motif_risks = risks
        profile.games_played += 1
        profile.updated_at = datetime.now(timezone.utc)
        
        self.db.add(profile)
        self.db.commit()

    def predict_error_probability(self, user_id: str, fen: str, move_uci: str) -> float:
        """Predict the probability that the user will err in the resulting position."""
        profile = self.get_profile(user_id)
        risks = profile["motif_risks"]
        
        # Placeholder: In a real system, we'd classify the position (fen + move) 
        # for motifs (e.g. "knight fork available") and check against user's risk profile.
        
        base_error_prob = 0.1
        
        # If user is known to blunder early, increase risk in opening
        board = chess.Board(fen)
        if board.fullmove < 10 and risks.get("early_blunder", 0) > 0.5:
            base_error_prob += 0.2

        return min(0.9, base_error_prob)
