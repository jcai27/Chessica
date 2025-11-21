"""Lightweight opening recognition based on UCI move prefixes."""

from __future__ import annotations

from typing import List, Dict, Optional

OPENINGS: List[Dict[str, object]] = [
    {"eco": "C60", "name": "Ruy Lopez", "uci": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]},
    {"eco": "C50", "name": "Italian Game", "uci": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]},
    {"eco": "B30", "name": "Sicilian Defence", "uci": ["e2e4", "c7c5"]},
    {"eco": "B90", "name": "Sicilian Najdorf", "uci": ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "a7a6"]},
    {"eco": "B12", "name": "Caro-Kann Defence", "uci": ["e2e4", "c7c6", "d2d4", "d7d5"]},
    {"eco": "C00", "name": "French Defence", "uci": ["e2e4", "e7e6", "d2d4", "d7d5"]},
    {"eco": "B01", "name": "Scandinavian Defence", "uci": ["e2e4", "d7d5"]},
    {"eco": "D30", "name": "Queen's Gambit Declined", "uci": ["d2d4", "d7d5", "c2c4", "e7e6"]},
    {"eco": "D10", "name": "Slav Defence", "uci": ["d2d4", "d7d5", "c2c4", "c7c6"]},
    {"eco": "E60", "name": "King's Indian Defence", "uci": ["d2d4", "g8f6", "c2c4", "g7g6"]},
    {"eco": "D02", "name": "London System", "uci": ["d2d4", "d7d5", "c1f4"]},
    {"eco": "E21", "name": "Nimzo-Indian Defence", "uci": ["d2d4", "g8f6", "c2c4", "e7e6", "b1c3", "f8b4"]},
]


def detect_opening(moves: List[str]) -> Optional[Dict[str, object]]:
    """Return the longest matching opening dict for the given UCI moves."""
    best: Optional[Dict[str, object]] = None
    for entry in OPENINGS:
        seq: List[str] = entry["uci"]  # type: ignore[assignment]
        if len(moves) < len(seq):
            # still allow shorter lines if fully matching
            compare = moves
        else:
            compare = moves[: len(seq)]
        if compare[: len(seq)] == seq[: len(compare)]:
            if not best or len(seq) > len(best["uci"]):  # type: ignore[index]
                best = entry
    return best
