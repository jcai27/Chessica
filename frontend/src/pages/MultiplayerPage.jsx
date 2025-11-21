import { useEffect, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api } from "../lib/api";
import { DEFAULT_TIME_CONTROL, WS_BASE } from "../lib/config";
import { formatEval, describeEval, formatMs } from "../lib/format";

const queueDefaults = {
  player_id: "",
  color: "auto",
  initial_ms: DEFAULT_TIME_CONTROL.initial_ms,
  increment_ms: DEFAULT_TIME_CONTROL.increment_ms,
};

function MultiplayerPage() {
  const chessRef = useRef(new Chess());
  const notationRef = useRef(new Chess());
  const streamRef = useRef(null);
  const pollRef = useRef(null);

  const [form, setForm] = useState(queueDefaults);
  const [sessionId, setSessionId] = useState("");
  const [playerColor, setPlayerColor] = useState("white");
  const [queueStatus, setQueueStatus] = useState("Not queued.");
  const [fen, setFen] = useState(chessRef.current.fen());
  const [clocks, setClocks] = useState(DEFAULT_TIME_CONTROL);
  const [movePairs, setMovePairs] = useState([]);
  const [message, setMessage] = useState("");
  const [matchInfo, setMatchInfo] = useState("");
  const [analysis, setAnalysis] = useState([]);
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [coachSummary, setCoachSummary] = useState("");
  const [coachLoading, setCoachLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("match");

  useEffect(() => {
    return () => {
      streamRef.current?.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const applyNotation = (uci) => {
    const move = notationRef.current.move({
      from: uci.slice(0, 2),
      to: uci.slice(2, 4),
      promotion: uci.length > 4 ? uci.slice(4) : undefined,
    });
    if (!move) return;
    setMovePairs((prev) => {
      const next = [...prev];
      if (move.color === "w") {
        next.push({ number: next.length + 1, white: move.san, black: null });
      } else if (next.length === 0) {
        next.push({ number: 1, white: "...", black: move.san });
      } else {
        const last = next[next.length - 1];
        if (last.black) {
          next.push({ number: next.length + 1, white: "...", black: move.san });
        } else {
          last.black = move.san;
        }
      }
      return next;
    });
  };

  const rebuildNotation = (moves) => {
    notationRef.current.reset();
    setMovePairs([]);
    (moves || []).forEach(applyNotation);
  };

  const connectStream = (id) => {
    streamRef.current?.close();
    const ws = new WebSocket(`${WS_BASE}/sessions/${id}/stream`);
    streamRef.current = ws;
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "player_move" && data.payload?.uci) {
          const { uci, game_state, clocks: updatedClocks } = data.payload;
          chessRef.current.load(game_state.fen);
          setFen(game_state.fen);
          setClocks(updatedClocks || clocks);
          applyNotation(uci);
        }
        if (data.type === "game_over" && data.payload?.game_state?.fen) {
          chessRef.current.load(data.payload.game_state.fen);
          setFen(data.payload.game_state.fen);
          setMessage(data.payload.message || "Game over.");
        }
      } catch {
        // ignore malformed frames
      }
    };
  };

  const pollQueue = (playerId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.queueStatus(playerId);
        if (status.status === "matched" && status.session_id) {
          clearInterval(pollRef.current);
          await handleMatched(status.session_id, status.player_color, status.opponent_id);
        } else {
          setQueueStatus(status.message || "Waiting...");
        }
      } catch (err) {
        setQueueStatus(err.message);
      }
    }, 2000);
  };

  const handleMatched = async (id, color, opponentId) => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
    }
    setSessionId(id);
    setPlayerColor(color || "white");
    setQueueStatus("Matched!");
    setMatchInfo(`vs ${opponentId || "pending"} • You are ${color}`);
    const detail = await api.sessionDetail(id);
    chessRef.current.load(detail.fen);
    setFen(detail.fen);
    rebuildNotation(detail.moves || []);
    setClocks(detail.clocks || DEFAULT_TIME_CONTROL);
    connectStream(id);
    await refreshAnalysis(id);
  };

  const handleQueue = async (event) => {
    event.preventDefault();
    setMessage("");
    setQueueStatus("Joining queue...");
    try {
      const payload = {
        player_id: form.player_id.trim(),
        color: form.color,
        time_control: { initial_ms: Number(form.initial_ms), increment_ms: Number(form.increment_ms) },
      };
      const res = await api.queueJoin(payload);
      if (res.status === "matched" && res.session_id) {
        await handleMatched(res.session_id, res.player_color, res.opponent_id);
      } else {
        setQueueStatus(res.message || "Queued");
        pollQueue(payload.player_id);
      }
    } catch (err) {
      setQueueStatus("Queue failed.");
      setMessage(err.message);
    }
  };

  const leaveQueue = async () => {
    if (!form.player_id) return;
    try {
      await api.queueLeave(form.player_id);
      setQueueStatus("Not queued.");
      if (pollRef.current) clearInterval(pollRef.current);
    } catch (err) {
      setMessage(err.message);
    }
  };

  const handleDrop = async (sourceSquare, targetSquare, piece) => {
    if (!sessionId) return false;
    const turn = chessRef.current.turn() === "w" ? "white" : "black";
    if (turn !== playerColor) return false;
    const promotionRank = piece.startsWith("w") ? "8" : "1";
    const wantsPromotion = targetSquare.endsWith(promotionRank) && piece.toLowerCase().startsWith("p");
    const promotion = wantsPromotion
      ? (() => {
          const choice = window.prompt("Promote to (q, r, b, n):", "q")?.toLowerCase();
          if (!choice || !["q", "r", "b", "n"].includes(choice)) return null;
          return choice;
        })()
      : undefined;
    if (wantsPromotion && !promotion) return false;
    const move = chessRef.current.move({ from: sourceSquare, to: targetSquare, promotion });
    if (!move) return false;
    const uci = `${sourceSquare}${targetSquare}${promotion || ""}`;
    const prevFen = chessRef.current.fen();
    setFen(prevFen);
    applyNotation(uci);
    try {
      const res = await api.multiplayerMove(sessionId, {
        uci,
        player_id: form.player_id,
        client_ts: new Date().toISOString(),
        clock: clocks,
      });
      if (res.game_state?.fen) {
        chessRef.current.load(res.game_state.fen);
        setFen(res.game_state.fen);
      }
      setClocks(res.clocks || clocks);
      if (res.result) {
        setMessage(res.message || "Game finished.");
      }
      return true;
    } catch (err) {
      chessRef.current.undo();
      notationRef.current.undo();
      setFen(chessRef.current.fen());
      setMessage(err.message);
      return false;
    }
  };

  const action = async (type) => {
    if (!sessionId) return;
    try {
      const res = await api.multiplayerAction(sessionId, type);
      if (res.game_state?.fen) {
        chessRef.current.load(res.game_state.fen);
        setFen(res.game_state.fen);
      }
      setMessage(res.message || `${type} sent.`);
    } catch (err) {
      setMessage(err.message);
    }
  };

  const runCoach = async () => {
    if (!sessionId) return;
    setCoachLoading(true);
    setCoachSummary("");
    try {
      const data = await api.coach(sessionId);
      setCoachSummary(data.summary || "");
    } catch (err) {
      setCoachSummary(err.message || "Coach summary unavailable.");
    } finally {
      setCoachLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="page-grid">
        <section className="card board-card minimal">
          <div className="board-wrap">
            <div className="clock-bar top-clock">
              <div className="player-meta">
                <span className="muted">{playerColor === "white" ? "Opponent (Black)" : "Opponent (White)"}</span>
              </div>
              <span className="pill">{formatMs(playerColor === "white" ? clocks.engine_ms : clocks.player_ms)}</span>
            </div>
            <div className="board-shell-react">
              <Chessboard
                id="multiplayer-board"
                position={fen}
                onPieceDrop={handleDrop}
                boardOrientation={playerColor}
                animationDuration={150}
                customBoardStyle={{ borderRadius: 12, boxShadow: "0 12px 26px rgba(0,0,0,0.35)" }}
              />
            </div>
            <div className="clock-bar bottom-clock">
              <span className="pill">{formatMs(playerColor === "white" ? clocks.player_ms : clocks.engine_ms)}</span>
              <div className="player-meta">
                <strong>You</strong>
                <span className="muted">{playerColor === "white" ? "White" : "Black"}</span>
              </div>
            </div>
            <div className="inline-actions compact align-right">
              <button type="button" className="secondary" disabled={!sessionId} onClick={() => action("resign")}>
                Resign
              </button>
              <button type="button" className="secondary" disabled={!sessionId} onClick={() => action("draw")}>
                Offer Draw
              </button>
              <button type="button" className="secondary" disabled={!sessionId} onClick={() => action("abort")}>
                Abort
              </button>
              <span className="muted tiny">{message || matchInfo || queueStatus}</span>
            </div>
          </div>
        </section>

        <div className="side-stack">
          <header className="card hero hero-card">
            <div className="hero-title">
              <div className="badge">
                <span>⚡</span>
              </div>
              <div>
                <h1>Online Play</h1>
                <p>Queue for opponents, stream moves, and keep clocks in sync.</p>
                <small className="muted">{sessionId ? `Session ${sessionId}` : "Not matched"}</small>
              </div>
            </div>
            <span className="pill">Multiplayer</span>
          </header>

          <section className="card tab-card">
            <div className="tab-bar">
              {[
                { key: "match", label: "Match" },
                { key: "moves", label: "Move List" },
                { key: "coach", label: "Coach Insight" },
              ].map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  className={`tab-button ${activeTab === tab.key ? "active" : ""}`}
                  onClick={() => setActiveTab(tab.key)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="tab-panel">
              {activeTab === "match" && (
                <form className="controls-form" onSubmit={handleQueue}>
                  <label className="select-field">
                    <span>Player ID</span>
                    <input
                      type="text"
                      value={form.player_id}
                      required
                      onChange={(e) => setForm((prev) => ({ ...prev, player_id: e.target.value }))}
                      placeholder="your-handle"
                    />
                  </label>
                  <label className="select-field">
                    <span>Color</span>
                    <select value={form.color} onChange={(e) => setForm((prev) => ({ ...prev, color: e.target.value }))}>
                      <option value="auto">Auto</option>
                      <option value="white">White</option>
                      <option value="black">Black</option>
                    </select>
                  </label>
                  <label className="select-field">
                    <span>Initial (ms)</span>
                    <input
                      type="number"
                      value={form.initial_ms}
                      onChange={(e) => setForm((prev) => ({ ...prev, initial_ms: e.target.value }))}
                      min="60000"
                      step="60000"
                    />
                  </label>
                  <label className="select-field">
                    <span>Increment (ms)</span>
                    <input
                      type="number"
                      value={form.increment_ms}
                      onChange={(e) => setForm((prev) => ({ ...prev, increment_ms: e.target.value }))}
                      min="0"
                      step="1000"
                    />
                  </label>
                  <div className="difficulty-indicator">{queueStatus}</div>
                  <div className="inline-actions compact">
                    <button type="submit">Join Queue</button>
                    <button type="button" className="secondary" onClick={leaveQueue}>
                      Leave Queue
                    </button>
                  </div>
                </form>
              )}

              {activeTab === "moves" && (
                <ol className="analysis-list">
                  {movePairs.length === 0 && <li className="muted">No moves yet.</li>}
                  {movePairs.map((pair) => (
                    <li key={pair.number} className="analysis-item">
                      <strong>
                        {pair.number}. {pair.white || "..."} {pair.black || "..."}
                      </strong>
                    </li>
                  ))}
                </ol>
              )}

              {activeTab === "coach" && (
                <div className="stack">
                  <button type="button" disabled={!sessionId || coachLoading} onClick={runCoach}>
                    {coachLoading ? "Generating..." : "Explain Position"}
                  </button>
                  {coachSummary ? (
                    <p className="muted">{coachSummary}</p>
                  ) : (
                    <p className="muted">Request a coach summary after moves are played.</p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default MultiplayerPage;
