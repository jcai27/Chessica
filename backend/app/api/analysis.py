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

    moves = [
        AnalysisMove(
            ply=index + 1,
            player_move=move,
            engine_reply="c5d4",
            objective_eval_cp=-34 + index,
            exploit_gain_cp=20 + index,
            motifs=["fork pressure", "time squeeze"],
            explanation="Steers into motifs aligned with recent opponent errors.",
        )
        for index, move in enumerate(record.moves[-3:])
    ]

    summary = AnalysisSummary(
        induced_blunders=len(moves) // 2,
        eval_tradeoff_cp=sum(m.exploit_gain_cp for m in moves),
        themes=["fork pressure", "time squeeze"],
    )

    return AnalysisResponse(session_id=session_id, moves=moves, summary=summary)
