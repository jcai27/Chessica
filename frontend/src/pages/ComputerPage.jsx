import { useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api } from "../lib/api";
import { API_BASE, DEFAULT_TIME_CONTROL, WS_BASE } from "../lib/config";
import { DIFFICULTY_PRESETS, describePreset } from "../lib/difficulties";
import { describeEval, formatEval } from "../lib/format";

function ComputerPage() {
  const chessRef = useRef(new Chess());
  const notationRef = useRef(new Chess());
  const streamRef = useRef(null);

  const [fen, setFen] = useState(chessRef.current.fen());
  const [session, setSession] = useState(null);
  const [analysis, setAnalysis] = useState([]);
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [movePairs, setMovePairs] = useState([]);
  const [coachSummary, setCoachSummary] = useState("");
  const [coachLoading, setCoachLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("controls");
  const [colorChoice, setColorChoice] = useState("auto");
  const [exploitMode, setExploitMode] = useState("auto");
  const [difficulty, setDifficulty] = useState("advanced");
  const [statusText, setStatusText] = useState("No active session.");
  const [pending, setPending] = useState(false);
  const [latestEval, setLatestEval] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    return () => {
      streamRef.current?.close();
    };
  }, []);

  const orientation = useMemo(() => session?.player_color || "white", [session?.player_color]);

  const shareUrl = useMemo(() => {
    if (!session?.session_id) return "";
    const url = new URL(window.location.href);
    url.pathname = "/replay";
    url.searchParams.set("session", session.session_id);
    return url.toString();
  }, [session?.session_id]);

  const copyShareLink = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard?.writeText(shareUrl);
      setMessage("Replay link copied.");
    } catch (err) {
      setMessage(err.message || "Unable to copy link.");
    }
  };

  const connectStream = (sessionId) => {
    streamRef.current?.close();
    const ws = new WebSocket(`${WS_BASE}/sessions/${sessionId}/stream`);
    streamRef.current = ws;
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "game_over" && data.payload?.game_state?.fen) {
          chessRef.current.load(data.payload.game_state.fen);
          setFen(chessRef.current.fen());
          setStatusText(data.payload.message || "Game over.");
          setMessage(data.payload.message || "");
        }
      } catch {
        // ignore noisy frames
      }
    };
  };

  const resetBoards = () => {
    chessRef.current.reset();
    notationRef.current.reset();
    setFen(chessRef.current.fen());
    setMovePairs([]);
    setAnalysis([]);
    setAnalysisSummary(null);
    setCoachSummary("");
    setLatestEval(null);
  };

  const applyNotation = (uci) => {
    if (!uci) return;
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

  const refreshAnalysis = async (sessionId) => {
    if (!sessionId) return;
    try {
      const data = await api.analysis(sessionId);
      setAnalysis(data.moves || []);
      setAnalysisSummary(data.summary || null);
    } catch (err) {
      setMessage(err.message);
    }
  };

  const requestEngineMove = async (detail) => {
    const target = detail || session;
    if (!target?.session_id) return;
    const engineTurn = chessRef.current.turn() === (target.engine_color === "white" ? "w" : "b");
    if (!engineTurn) return;
    try {
      const res = await api.move(target.session_id, {
        uci: null,
        client_ts: new Date().toISOString(),
        clock: target.clocks || DEFAULT_TIME_CONTROL,
        telemetry: { ui_version: "react" },
      });
      if (res.game_state?.fen) {
        chessRef.current.load(res.game_state.fen);
        setFen(res.game_state.fen);
      }
      if (res.engine_move) {
        applyNotation(res.engine_move);
      }
      setLatestEval(res.engine_eval_cp);
    } catch (err) {
      setMessage(err.message || "Engine move failed.");
    }
  };

  const handleStart = async (event) => {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      const payload = {
        variant: "standard",
        color: colorChoice,
        exploit_mode: exploitMode,
        difficulty,
        time_control: DEFAULT_TIME_CONTROL,
      };
      const created = await api.createSession(payload);
      const detail = await api.sessionDetail(created.session_id);
      setSession(detail);
      setStatusText(
        `Session ${detail.session_id} • Engine plays ${detail.engine_color} • ${describePreset(detail.difficulty)}`,
      );
      resetBoards();
      chessRef.current.load(detail.fen);
      setFen(detail.fen);
      rebuildNotation(detail.moves || []);
      applyOpponentProfile(detail.opponent_profile);
      connectStream(detail.session_id);
      await refreshAnalysis(detail.session_id);
      await requestEngineMove(detail);
    } catch (err) {
      setMessage(err.message || "Unable to start session.");
    } finally {
      setPending(false);
    }
  };

  const applyOpponentProfile = (profile) => {
    if (!profile) return;
    const tactical = Math.round((profile.style?.tactical ?? 0) * 100);
    const risk = Math.round((profile.style?.risk ?? 0) * 100);
    setMessage(`Opponent profile: tactical ${tactical}% · risk ${risk}%`);
  };

  const runCoachSummary = async () => {
    if (!session?.session_id) return;
    setCoachLoading(true);
    setCoachSummary("");
    try {
      const data = await api.coach(session.session_id);
      setCoachSummary(data.summary || "");
    } catch (err) {
      setCoachSummary(err.message || "Coach summary unavailable.");
    } finally {
      setCoachLoading(false);
    }
  };

  const handleDrop = async (sourceSquare, targetSquare, piece) => {
    if (!session?.session_id) return false;
    if (pending) return false;
    const promotionRank = piece.startsWith("w") ? "8" : "1";
    const wantsPromotion = targetSquare.endsWith(promotionRank) && piece.toLowerCase().startsWith("p");
    const promotion = wantsPromotion ? "q" : undefined;
    const move = chessRef.current.move({ from: sourceSquare, to: targetSquare, promotion });
    if (!move) return false;
    const uci = `${sourceSquare}${targetSquare}${promotion || ""}`;
    setFen(chessRef.current.fen());
    applyNotation(uci);
    try {
      await submitMove(uci);
      return true;
    } catch (err) {
      chessRef.current.undo();
      notationRef.current.undo();
      setFen(chessRef.current.fen());
      setMessage(err.message);
      return false;
    }
  };

  const submitMove = async (uci) => {
    if (!session?.session_id) throw new Error("No active session.");
    const clocks = session?.clocks || { player_ms: 300000, engine_ms: 300000 };
    const payload = {
      uci,
      client_ts: new Date().toISOString(),
      clock: clocks,
      telemetry: { ui_version: "react" },
    };
    const response = await api.move(session.session_id, payload);
    if (response.game_state?.fen) {
      chessRef.current.load(response.game_state.fen);
      setFen(response.game_state.fen);
    }
    if (response.engine_move) {
      applyNotation(response.engine_move);
    }
    setLatestEval(response.engine_eval_cp);
    setMessage(response.message || "");
    setSession((prev) => ({ ...(prev || session), fen: response.game_state?.fen || fen, status: response.result ? "completed" : "active" }));
    await refreshAnalysis(session.session_id);
    if (response.result) {
      setStatusText(response.message || `Game over (${response.result})`);
    }
  };

  const downloadPgn = async () => {
    if (!session?.session_id) return;
    const pgn = await api.pgn(session.session_id);
    const blob = new Blob([pgn], { type: "application/x-chess-pgn" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${session.session_id}.pgn`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="app">
      <div className="page-grid">
        <section className="card board-card">
          <div className="board-wrap">
            <div className="board-shell-react">
              <Chessboard
                id="computer-board"
                position={fen}
                onPieceDrop={handleDrop}
                boardOrientation={orientation}
                animationDuration={150}
                customBoardStyle={{ borderRadius: 16, boxShadow: "0 12px 26px rgba(0,0,0,0.35)" }}
              />
            </div>
            <div className="inline-actions compact">
              <button type="button" className="secondary" disabled={!session?.session_id} onClick={downloadPgn}>
                Download PGN
              </button>
              <button type="button" className="secondary" disabled={!shareUrl} onClick={copyShareLink}>
                Copy Replay Link
              </button>
              <span className="muted tiny">{message || statusText}</span>
            </div>
          </div>
        </section>

        <div className="side-stack">
          <header className="card hero hero-card">
            <div className="hero-title">
              <div className="badge">
                <span>♟︎</span>
              </div>
              <div>
                <h1>Chessica Control Room</h1>
                <p>Exploit-aware sessions with offline-ready assets, coach summaries, and difficulty presets.</p>
                <small className="muted">
                  {session?.session_id ? `Session ${session.session_id} · Engine plays ${session.engine_color}` : "No active session"}
                </small>
              </div>
            </div>
            <span className="pill">{session ? "Active" : "Setup"}</span>
          </header>

          <section className="card tab-card">
            <div className="tab-bar">
              {[
                { key: "controls", label: "Controls" },
                { key: "moves", label: "Move List" },
                { key: "analysis", label: "Analysis" },
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
              {activeTab === "controls" && (
                <form className="controls-form" onSubmit={handleStart}>
                  <label className="select-field">
                    <span>Color</span>
                    <select value={colorChoice} onChange={(e) => setColorChoice(e.target.value)}>
                      <option value="auto">Auto</option>
                      <option value="white">White</option>
                      <option value="black">Black</option>
                    </select>
                  </label>
                  <label className="select-field">
                    <span>Exploit Mode</span>
                    <select value={exploitMode} onChange={(e) => setExploitMode(e.target.value)}>
                      <option value="auto">Auto</option>
                      <option value="on">On</option>
                      <option value="off">Off</option>
                    </select>
                  </label>
                  <label className="select-field">
                    <span>Difficulty</span>
                    <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                      {DIFFICULTY_PRESETS.map((preset) => (
                        <option key={preset.key} value={preset.key}>
                          {preset.name} (~{preset.rating})
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="difficulty-indicator">
                    <span>{describePreset(difficulty)}</span>
                  </div>
                  <button type="submit" disabled={pending}>
                    {pending ? "Starting..." : session ? "Restart Session" : "Start Session"}
                  </button>
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

              {activeTab === "analysis" && (
                <div className="stack">
                  {analysisSummary && (
                    <div className="summary-block">
                      <div className="panel-title">
                        <strong>Induced blunders</strong>
                        <span className="pill">{analysisSummary.induced_blunders}</span>
                      </div>
                      <div className="panel-title">
                        <strong>Eval tradeoff</strong>
                        <span className="pill">{analysisSummary.eval_tradeoff_cp} cp</span>
                      </div>
                      <div className="tag-row">
                        {(analysisSummary.themes || []).map((theme) => (
                          <span key={theme} className="tag">
                            {theme}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <button
                    type="button"
                    className="secondary"
                    disabled={!session?.session_id}
                    onClick={() => refreshAnalysis(session?.session_id)}
                  >
                    Refresh
                  </button>
                  <ul className="analysis-list">
                    {analysis.length === 0 && <li className="muted">No annotated moves yet.</li>}
                    {analysis.map((move) => (
                      <li key={`${move.ply}-${move.player_move}-${move.engine_reply}`} className="analysis-item">
                        <strong>
                          {move.ply}. {move.player_move || "..."} → {move.engine_reply || "..."}
                        </strong>
                        <div className="muted">
                          Eval {formatEval(move.objective_eval_cp)} · Exploit {formatEval(move.exploit_gain_cp)}
                        </div>
                        <div className="tag-row">
                          {move.motifs?.map((motif) => (
                            <span key={motif} className="tag">
                              {motif}
                            </span>
                          ))}
                        </div>
                        <p className="muted">{move.explanation}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {activeTab === "coach" && (
                <div className="stack">
                  <button type="button" disabled={!session?.session_id || coachLoading} onClick={runCoachSummary}>
                    {coachLoading ? "Generating..." : "Explain Position"}
                  </button>
                  <div className="insight-eval">
                    <div className="eval-score">{formatEval(latestEval ?? 0)}</div>
                    <span>{describeEval(latestEval ?? 0)}</span>
                    <p className="muted">{coachSummary || "No coach summary yet."}</p>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default ComputerPage;
