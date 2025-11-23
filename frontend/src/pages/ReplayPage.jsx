import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api } from "../lib/api";
import { useSettings, BOARD_THEMES } from "../lib/settings";

function ReplayPage() {
  const { settings } = useSettings();
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
      <div className="page-grid">
        <section className="card board-card">
          <div className="board-wrap">
            <div className="clock-bar top-clock">
              <div className="player-meta">
                <span className="muted">{replay ? `Session ${replay.session_id}` : "No session"}</span>
                <span className="muted">{replay?.result || replay?.status || "Idle"}</span>
              </div>
              <span className="pill">Move {current}/{replay?.moves?.length || 0}</span>
            </div>
            <div className="board-shell-react">
              <Chessboard
                id="replay-board"
                position={fen}
                boardOrientation={replay?.player_color || "white"}
                arePiecesDraggable={false}
                animationDuration={settings.animationsEnabled ? settings.animationSpeed : 0}
                customBoardStyle={{
                  borderRadius: 16,
                  boxShadow: "0 12px 26px rgba(0,0,0,0.35)"
                }}
                customDarkSquareStyle={{ backgroundColor: BOARD_THEMES[settings.boardTheme].dark }}
                customLightSquareStyle={{ backgroundColor: BOARD_THEMES[settings.boardTheme].light }}
                showBoardNotation={settings.showCoordinates}
              />
            </div>
            <div className="clock-bar bottom-clock">
              <div className="inline-actions compact">
                <button type="button" onClick={() => stepTo(0)}>
                  ⏮ Start
                </button>
                <button type="button" onClick={() => stepTo(current - 1)}>
                  ◀ Prev
                </button>
                <button type="button" onClick={() => stepTo(current + 1)}>
                  Next ▶
                </button>
                <button type="button" onClick={() => stepTo(replay?.moves?.length || 0)}>
                  End ⏭
                </button>
              </div>
              <div className="player-meta">
                <span className="muted">Replay Controls</span>
              </div>
            </div>
            <div className="inline-actions compact align-right">
              <button type="button" className="secondary" disabled={!sessionId} onClick={downloadPgn}>
                Download PGN
              </button>
              <button type="button" className="secondary" onClick={copyLink} disabled={!sessionId}>
                Copy Link
              </button>
              <span className="muted tiny">{message || "Use controls to navigate"}</span>
            </div>
          </div>
        </section>

        <div className="side-stack">
          <header className="card hero hero-card">
            <div className="hero-title">
              <div className="badge">
                <span>▶</span>
              </div>
              <div>
                <h1>Game Replay</h1>
                <p>Step through any finished session, share a link, or export PGN.</p>
                <small className="muted">
                  {replay ? `Reviewing: ${replay.session_id}` : "No session loaded"}
                </small>
              </div>
            </div>
            <span className="pill">{replay ? "Loaded" : "Idle"}</span>
          </header>

          <section className="card tab-card">
            <div className="tab-bar">
              <button type="button" className="tab-button active">
                Move List
              </button>
              <button type="button" className="tab-button">
                Load Session
              </button>
            </div>

            <div className="tab-panel">
              <div className="stack">
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
                      placeholder="sess_xxx or paste replay URL"
                      required
                    />
                  </label>
                  <button type="submit">Load Replay</button>
                </form>

                <ul className="analysis-list">
                  {!replay?.moves?.length && <li className="muted">No moves yet. Load a session to begin.</li>}
                  {replay?.moves?.map((entry, idx) => (
                    <li
                      key={`${entry.ply}-${entry.uci}`}
                      className={`analysis-item ${idx === current - 1 ? "active" : ""}`}
                      style={{ cursor: "pointer" }}
                      onClick={() => stepTo(idx + 1)}
                    >
                      <strong>
                        {entry.ply}. {entry.san || entry.uci}
                      </strong>
                      {entry.eval_cp !== undefined && (
                        <div className="muted">
                          Eval: {entry.eval_cp > 0 ? "+" : ""}{(entry.eval_cp / 100).toFixed(2)}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default ReplayPage;
