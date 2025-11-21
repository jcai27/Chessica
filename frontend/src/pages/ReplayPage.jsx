import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api } from "../lib/api";

function ReplayPage() {
  const location = useLocation();
  const chessRef = useRef(new Chess());
  const [sessionId, setSessionId] = useState("");
  const [replay, setReplay] = useState(null);
  const [fen, setFen] = useState(chessRef.current.fen());
  const [current, setCurrent] = useState(0);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionParam = params.get("session");
    if (sessionParam) {
      setSessionId(sessionParam);
      loadReplay(sessionParam);
    }
  }, [location.search]);

  const loadReplay = async (id) => {
    setMessage("");
    try {
      const data = await api.replay(id);
      setReplay(data);
      chessRef.current.load(data.initial_fen);
      setFen(data.initial_fen);
      setCurrent(0);
    } catch (err) {
      setMessage(err.message || "Failed to load replay.");
    }
  };

  const stepTo = (index) => {
    if (!replay) return;
    chessRef.current.load(replay.initial_fen || replay.fen || "");
    const bounded = Math.max(0, Math.min(index, replay.moves.length));
    for (let i = 0; i < bounded; i += 1) {
      const entry = replay.moves[i];
      if (!entry?.uci) continue;
      chessRef.current.move({
        from: entry.uci.slice(0, 2),
        to: entry.uci.slice(2, 4),
        promotion: entry.uci.length > 4 ? entry.uci.slice(4) : undefined,
      });
    }
    setCurrent(bounded);
    setFen(chessRef.current.fen());
  };

  const copyLink = async () => {
    if (!sessionId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("session", sessionId);
    try {
      await navigator.clipboard?.writeText(url.toString());
      setMessage("Replay link copied.");
    } catch (err) {
      setMessage(err.message || "Unable to copy link.");
    }
  };

  const downloadPgn = async () => {
    if (!sessionId) return;
    const pgn = await api.pgn(sessionId);
    const blob = new Blob([pgn], { type: "application/x-chess-pgn" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${sessionId}.pgn`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-title">
          <div className="badge">
            <span>▶</span>
          </div>
          <div>
            <h1>Replay</h1>
            <p>Step through any finished session, share a link, or export PGN.</p>
          </div>
        </div>
        <span className="pill">Review</span>
      </header>

      <section className="card controls">
        <form
          className="controls-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (sessionId) loadReplay(sessionId);
          }}
        >
          <label className="select-field">
            <span>Session ID</span>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="sess_xxx"
              required
            />
          </label>
          <button type="submit">Load Replay</button>
          <button type="button" className="secondary" onClick={copyLink} disabled={!sessionId}>
            Copy link
          </button>
          <button type="button" className="secondary" onClick={downloadPgn} disabled={!sessionId}>
            Download PGN
          </button>
        </form>
        <div className="difficulty-indicator">{message || "Paste a session id to begin."}</div>
      </section>

      <main className="replay-layout">
        <section className="card board-card">
          <div className="card-header">
            <div>
              <h2>Replay Board</h2>
              <span className="muted">{replay ? replay.result || replay.status : "No game loaded."}</span>
            </div>
            <span className="status-chip">{replay ? replay.session_id : "Idle"}</span>
          </div>
          <div className="board-wrap">
            <div className="board-shell-react">
              <Chessboard
                id="replay-board"
                position={fen}
                boardOrientation={replay?.player_color || "white"}
                arePiecesDraggable={false}
                customBoardStyle={{ borderRadius: 16, boxShadow: "0 12px 26px rgba(0,0,0,0.35)" }}
              />
            </div>
            <div className="replay-controls">
              <button type="button" onClick={() => stepTo(0)}>
                Start
              </button>
              <button type="button" onClick={() => stepTo(current - 1)}>
                Prev
              </button>
              <button type="button" onClick={() => stepTo(current + 1)}>
                Next
              </button>
              <button type="button" onClick={() => stepTo(replay?.moves?.length || 0)}>
                End
              </button>
            </div>
            <div className="replay-meta">
              <span>
                Move {current}/{replay?.moves?.length || 0}
              </span>
            </div>
          </div>
        </section>

        <section className="card insight-card">
          <div className="card-header">
            <div>
              <h2>Move List</h2>
              <span className="muted">Tap a move to jump</span>
            </div>
          </div>
          <div className="replay-move-list">
            {replay?.moves?.map((entry, idx) => (
              <button
                key={`${entry.ply}-${entry.uci}`}
                type="button"
                className={idx === current ? "active" : ""}
                onClick={() => stepTo(idx + 1)}
              >
                {entry.ply}. {entry.san || entry.uci}
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default ReplayPage;
