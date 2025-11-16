"""Game analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query

from ..schemas import AnalysisMove, AnalysisResponse, AnalysisSummary
from ..store import store

router = APIRouter(prefix="/sessions", tags=["analysis"])


@router.get("/{session_id}/analysis", response_model=AnalysisResponse)
def get_analysis(
    session_id: str = Path(..., description="Session identifier"),
    depth: int = Query(12, ge=4, le=40),
    perspective: str = Query("exploit", pattern="^(objective|exploit)$"),
) -> AnalysisResponse:
    try:
        record = store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    recent = record.move_log[-3:]
    moves = []
    for index, entry in enumerate(recent):
        uci = entry.get("uci", f"move_{index}")
        moves.append(
            AnalysisMove(
                ply=len(record.move_log) - len(recent) + index + 1,
                player_move=uci,
                engine_reply=entry.get("uci", "—"),
                objective_eval_cp=entry.get("eval_cp", 0),
                exploit_gain_cp=entry.get("delta_cp", 0),
                motifs=entry.get("themes", ["strategic motif"]),
                explanation=entry.get("commentary", "A thematic continuation."),
            )
        )

    summary = AnalysisSummary(
        induced_blunders=len(moves) // 2,
        eval_tradeoff_cp=sum(m.exploit_gain_cp for m in moves),
        themes=["fork pressure", "time squeeze"],
    )

    return AnalysisResponse(session_id=session_id, moves=moves, summary=summary)
