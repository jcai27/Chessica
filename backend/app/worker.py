import time
import threading
import queue
import logging
from typing import Dict, Any

from .engine import pick_engine_move, explain_engine_move, evaluate_position, build_move_insight, make_game_state, _score_to_cp
from .database import SessionLocal
from .models import SessionModel
from . import schemas
import chess

# Simple in-memory queue for demonstration. 
# In production, use Redis/Celery.
job_queue = queue.Queue()

logger = logging.getLogger(__name__)

def worker():
    """Background worker to process move requests."""
    while True:
        try:
            task = job_queue.get()
            if task is None:
                break
            
            process_move_task(task)
            job_queue.task_done()
        except Exception as e:
            logger.error(f"Worker failed: {e}")

def start_worker():
    t = threading.Thread(target=worker, daemon=True)
    t.start()

def enqueue_move_task(session_id: str, board_fen: str, difficulty: str, engine_rating: int, user_id: str | None):
    job_queue.put({
        "session_id": session_id,
        "fen": board_fen,
        "difficulty": difficulty,
        "engine_rating": engine_rating,
        "user_id": user_id
    })

def process_move_task(task: Dict[str, Any]):
    from .api.sessions import stream_manager, log_event
    
    session_id = task["session_id"]
    board = chess.Board(task["fen"])
    
    try:
        # This is the heavy operation
        move, score, confidence, profile_data = pick_engine_move(
            board, 
            task["difficulty"], 
            task["engine_rating"], 
            user_id=task["user_id"]
        )
        
        # We need to update the DB with the result
        # Note: This duplicates some logic from sessions.py, but that's inevitable when moving to async
        # For this "simple" version, we'll just broadcast the result and let the frontend 
        # (or a separate "complete_move" endpoint) handle the state update.
        # BUT, to be robust, the worker should really update the DB.
        
        with SessionLocal() as db:
            session = db.get(SessionModel, session_id)
            if not session:
                return

            # Apply move
            board.push_uci(move)
            session.fen = board.fen()
            
            # Update profile
            from .schemas import OpponentProfile
            profile = OpponentProfile(
                style=profile_data.get("style", {}),
                motif_risk=profile_data.get("motif_risks", {})
            )
            session.opponent_profile = profile.model_dump()
            
            # Log move
            # (Simplified for brevity - real implementation would need full insight generation)
            
            db.commit()
            
            # Broadcast
            payload = {
                "uci": move,
                "engine_eval_cp": score,
                "exploit_confidence": confidence,
                "fen": board.fen(),
                "opponent_profile": session.opponent_profile
            }
            
            # We need an async loop to send the websocket message
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(stream_manager.broadcast(session_id, {
                "type": "engine_move",
                "payload": payload
            }))
            loop.close()
            
    except Exception as e:
        logger.error(f"Task failed for session {session_id}: {e}")
