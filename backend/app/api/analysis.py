"""Game analysis endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from ..schemas import AnalysisMove, AnalysisResponse, AnalysisSummary
from ..store import store

router = APIRouter(prefix="/sessions", tags=["analysis"])


def _ordered_moves(move_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return move log sorted by ply, preserving insertion order as fallback."""
    indexed = []
    for idx, entry in enumerate(move_log):
        ply = entry.get("ply", idx + 1)
        indexed.append((ply, idx, entry))
    indexed.sort(key=lambda item: (item[0], item[1]))
    return [entry for _, _, entry in indexed]


def _pairwise_moves(move_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group moves into player/engine pairs so analysis shows a single ply with its reply.
    Handles sessions where the engine started first (no player move yet).
    """
    pairs: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    ordered = _ordered_moves(move_log)

    for entry in ordered:
        side = entry.get("side")
        is_player_side = side not in ("engine", "black")
        if is_player_side:
            current = {
                "ply": entry.get("ply", len(ordered) + 1),
                "player": entry,
                "engine": None,
            }
        else:
            if current and current.get("engine") is None:
                current["engine"] = entry
            else:
                pairs.append(
                    {
                        "ply": entry.get("ply", len(ordered) + 1),
                        "player": None,
                        "engine": entry,
                    }
                )
            current = None
        if is_player_side:
            pairs.append(current)
    return pairs


def _extract_move_label(entry: Optional[Dict[str, Any]]) -> str:
    if not entry:
        return "-"
    return entry.get("san") or entry.get("uci", "-")


def _extract_eval(entry: Optional[Dict[str, Any]]) -> int:
    if not entry:
        return 0
    return int(entry.get("eval_cp", 0))


def _extract_delta(entry: Optional[Dict[str, Any]]) -> int:
    if not entry:
        return 0
    return int(entry.get("delta_cp", 0))


def _collect_themes(player_entry: Optional[Dict[str, Any]], engine_entry: Optional[Dict[str, Any]]) -> List[str]:
    themes: List[str] = []
    for entry in (player_entry, engine_entry):
        if entry and entry.get("themes"):
            themes.extend([str(t) for t in entry.get("themes", []) if t])
    seen = set()
    unique: List[str] = []
    for theme in themes:
        if theme in seen:
            continue
        seen.add(theme)
        unique.append(theme)
    return unique or ["strategic motif"]


@router.get("/{session_id}/analysis", response_model=AnalysisResponse)
def get_analysis(
    session_id: str = Path(..., description="Session identifier"),
    depth: int = Query(12, ge=4, le=40),
    perspective: str = Query("exploit", pattern="^(objective|exploit)$"),
) -> AnalysisResponse:
    """
    Return a lightweight analysis built from the session move log.

    This pairs player moves with engine replies, surfaces stored eval/delta data,
    and respects perspective by hiding exploit deltas when "objective" is chosen.
    """
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    pairs = _pairwise_moves(record.move_log)
    moves: List[AnalysisMove] = []

    for pair in pairs:
        player_entry = pair.get("player")
        engine_entry = pair.get("engine")

        player_move = _extract_move_label(player_entry)
        engine_reply = _extract_move_label(engine_entry)

        eval_cp = _extract_eval(engine_entry or player_entry)
        exploit_gain = _extract_delta(engine_entry or player_entry)

        motifs = _collect_themes(player_entry, engine_entry)
        explanation = (
            (engine_entry or {}).get("commentary")
            or (player_entry or {}).get("commentary")
            or "A thematic continuation."
        )

        ply_candidates = [
            val
            for val in (
                (player_entry or {}).get("ply"),
                (engine_entry or {}).get("ply"),
                pair.get("ply"),
            )
            if val is not None
        ]
        ply_value = min(ply_candidates) if ply_candidates else len(moves) + 1

        moves.append(
            AnalysisMove(
                ply=ply_value,
                player_move=player_move,
                engine_reply=engine_reply,
                objective_eval_cp=eval_cp,
                exploit_gain_cp=exploit_gain if perspective == "exploit" else 0,
                motifs=motifs,
                explanation=explanation,
            )
        )

    player_blunders = sum(
        1
        for entry in _ordered_moves(record.move_log)
        if entry.get("side") == "player"
        and entry.get("verdict") in {"inaccuracy", "mistake", "blunder"}
    )

    summary = AnalysisSummary(
        induced_blunders=player_blunders,
        eval_tradeoff_cp=sum(move.exploit_gain_cp for move in moves),
        themes=["tactics", "pressure", "conversion"] if moves else ["no themes yet"],
    )

    return AnalysisResponse(session_id=session_id, moves=moves, summary=summary)
