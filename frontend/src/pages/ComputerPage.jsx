import { useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { api } from "../lib/api";
import { API_BASE, DEFAULT_TIME_CONTROL, WS_BASE } from "../lib/config";
import { DIFFICULTY_PRESETS, describePreset } from "../lib/difficulties";
import { describeEval, formatEval, formatMs } from "../lib/format";

const TIME_PRESETS = [
  { id: "blitz", label: "Blitz 5+0", time_control: { initial_ms: 300000, increment_ms: 0 } },
  { id: "rapid", label: "Rapid 10+0", time_control: { initial_ms: 600000, increment_ms: 0 } },
  { id: "classical", label: "Classical 30+0", time_control: { initial_ms: 1800000, increment_ms: 0 } },
];

const parseCoachSummary = (summary) => {
  const text = (summary || "").trim();
  if (!text) return [];
  const byNewline = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (byNewline.length > 1) return byNewline;
  return text
    .split(/(?<=[.!?])\s+/)
    .map((line) => line.trim())
    .filter(Boolean);
};

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
  const [coachData, setCoachData] = useState(null);
  const [activeTab, setActiveTab] = useState("controls");
  const [colorChoice, setColorChoice] = useState("auto");
  const [exploitMode, setExploitMode] = useState("auto");
  const [difficulty, setDifficulty] = useState("advanced");
  const [timePreset, setTimePreset] = useState("blitz");
  const [statusText, setStatusText] = useState("No active session.");
  const [pending, setPending] = useState(false);
  const [latestEval, setLatestEval] = useState(null);
  const [message, setMessage] = useState("");
  const [gameBanner, setGameBanner] = useState(null);
  const [pendingPromotion, setPendingPromotion] = useState(null);
  const coachLines = useMemo(() => parseCoachSummary(coachSummary), [coachSummary]);
  const coachPlans = coachData?.plans || [];
  const coachFeatures = coachData?.position_features;
  const coachOpening = coachData?.opening;
  const [coachView, setCoachView] = useState("ideas");

  useEffect(() => {
    return () => {
      streamRef.current?.close();
    };
  }, []);

  const orientation = useMemo(() => session?.player_color || "white", [session?.player_color]);
  const playerColor = orientation;
  const engineColor = playerColor === "white" ? "black" : "white";
  const playerMs = session?.clocks?.player_ms ?? 300000;
  const engineMs = session?.clocks?.engine_ms ?? 300000;

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
        if (data.type === "coach_update") {
          setCoachSummary(data.payload.summary || "");
          setCoachData(data.payload);
          if (typeof data.payload.eval_cp === "number") {
            setLatestEval(data.payload.eval_cp);
          }
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
      const tc = TIME_PRESETS.find((p) => p.id === timePreset)?.time_control || DEFAULT_TIME_CONTROL;
      const payload = {
        variant: "standard",
        color: colorChoice,
        exploit_mode: exploitMode,
        difficulty,
        time_control: tc,
      };
      const created = await api.createSession(payload);
      const detail = await api.sessionDetail(created.session_id);
      setSession(detail);
      setStatusText(`Session ${detail.session_id} • ${timePreset.toUpperCase()} • ${describePreset(detail.difficulty)}`);
      resetBoards();
      setGameBanner(null);
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
    setCoachData(null);
    try {
      const data = await api.coach(session.session_id);
      setCoachSummary(data.summary || "");
      setCoachData(data);
    } catch (err) {
      setCoachSummary(err.message || "Coach summary unavailable.");
    } finally {
      setCoachLoading(false);
    }
  };

  const selectMoveWithPromotion = (sourceSquare, targetSquare) => {
    const candidates = chessRef.current
      .moves({ verbose: true })
      .filter((m) => m.from === sourceSquare && m.to === targetSquare);
    if (!candidates.length) return null;
    const promoMoves = candidates.filter((m) => m.promotion);
    if (!promoMoves.length) return candidates[0];
    if (promoMoves.length === 1) return promoMoves[0];
    const options = promoMoves.map((m) => m.promotion).filter(Boolean);
    setPendingPromotion({ sourceSquare, targetSquare, options, promoMoves });
    return null;
  };

  const applyPromotionChoice = async (promo) => {
    if (!pendingPromotion) return;
    const { sourceSquare, targetSquare, promoMoves } = pendingPromotion;
    const selected = promoMoves.find((m) => m.promotion === promo) || promoMoves[0];
    setPendingPromotion(null);
    const move = chessRef.current.move(selected);
    if (!move) return false;
    const uci = `${sourceSquare}${targetSquare}${move.promotion || ""}`;
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

  const cancelPromotionChoice = () => {
    setPendingPromotion(null);
  };

  const handleDrop = async (sourceSquare, targetSquare, piece) => {
    if (!session?.session_id) return false;
    if (pending) return false;
    const selected = selectMoveWithPromotion(sourceSquare, targetSquare);
    if (!selected) return false;
    const move = chessRef.current.move(selected);
    if (!move) return false;
    const promotion = move.promotion ? move.promotion : "";
    const uci = `${sourceSquare}${targetSquare}${promotion}`;
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
      setGameBanner({
        title: response.winner === "player" ? "Victory" : response.winner === "engine" ? "Defeat" : "Draw",
        message:
          response.message ||
          `${response.result}${typeof response.player_rating_delta === "number" ? ` · Rating: ${response.player_rating_delta >= 0 ? "+" : ""}${response.player_rating_delta}` : ""}`,
      });
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
            <div className="clock-bar top-clock">
              <div className="player-meta">
                <span className="muted">Engine ({engineColor})</span>
                <span className="muted">{describePreset(session?.difficulty || difficulty)}</span>
              </div>
              <span className="pill">{formatMs(engineMs)}</span>
            </div>
            <div className="board-shell-react">
              <Chessboard
                id="computer-board"
                position={fen}
                onPieceDrop={handleDrop}
                boardOrientation={orientation}
                animationDuration={200}
                customBoardStyle={{
                  borderRadius: 16,
                  boxShadow: "0 12px 26px rgba(0,0,0,0.35)"
                }}
                customDarkSquareStyle={{ backgroundColor: "#779952" }}
                customLightSquareStyle={{ backgroundColor: "#edeed1" }}
                customPremoveDarkSquareStyle={{ backgroundColor: "#e67e22" }}
                customPremoveLightSquareStyle={{ backgroundColor: "#f39c12" }}
                showBoardNotation={true}
                boardWidth={560}
                arePiecesDraggable={!pendingPromotion && !gameBanner}
              />
            </div>
            {pendingPromotion && (
              <div className="promotion-panel">
                <span className="muted">Promote to:</span>
                <div className="inline-actions compact">
                  {pendingPromotion.options.map((opt) => (
                    <button key={opt} type="button" onClick={() => applyPromotionChoice(opt)}>
                      {opt.toUpperCase()}
                    </button>
                  ))}
                  <button type="button" className="secondary" onClick={cancelPromotionChoice}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
            {gameBanner && (
              <div className="game-banner">
                <strong>{gameBanner.title}</strong>
                <span className="muted">{gameBanner.message}</span>
              </div>
            )}
            <div className="clock-bar bottom-clock">
              <span className="pill">{formatMs(playerMs)}</span>
              <div className="player-meta">
                <strong>You</strong>
                <span className="muted">{playerColor}</span>
              </div>
            </div>
            <div className="inline-actions compact align-right">
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
                  <div className="time-preset-grid">
                    {TIME_PRESETS.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        className={`time-pill ${timePreset === preset.id ? "active" : ""}`}
                        onClick={() => setTimePreset(preset.id)}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
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
                  </div>
                  <div className="coach-tabs">
                    {[
                      { key: "ideas", label: "Ideas" },
                      { key: "risks", label: "Risks" },
                      { key: "candidates", label: "Candidates" },
                      { key: "summary", label: "Summary" },
                    ].map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        className={`coach-tab ${coachView === tab.key ? "active" : ""}`}
                        onClick={() => setCoachView(tab.key)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                  {coachView === "ideas" && (
                    <ul className="coach-lines">
                      {(coachData?.ideas || coachLines).map((line, idx) => (
                        <li key={`${line}-${idx}`}>{line}</li>
                      ))}
                      {!(coachData?.ideas || coachLines).length && <li className="muted">No ideas yet.</li>}
                    </ul>
                  )}
                  {coachView === "risks" && (
                    <ul className="coach-lines">
                      {(coachData?.risks || []).map((line, idx) => (
                        <li key={`${line}-${idx}`}>{line}</li>
                      ))}
                      {!(coachData?.risks || []).length && <li className="muted">No explicit risks flagged.</li>}
                    </ul>
                  )}
                  {coachView === "candidates" && (
                    <ul className="coach-lines">
                      {(coachData?.candidates || coachPlans).map((plan, idx) => (
                        <li key={`${plan.name || idx}-${idx}`}>
                          <strong>{plan.name || plan?.idea || "Plan"}</strong>{" "}
                          {plan.example_moves ? `(${(plan.example_moves || []).join(", ")})` : ""}
                        </li>
                      ))}
                      {!(coachData?.candidates || coachPlans).length && <li className="muted">No candidates yet.</li>}
                    </ul>
                  )}
                  {coachView === "summary" && (
                    <>
                      {coachLines.length ? (
                        <ul className="coach-lines">
                          {coachLines.map((line, idx) => (
                            <li key={`${line}-${idx}`}>{line}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="muted">No coach summary yet.</p>
                      )}
                    </>
                  )}
                  {coachOpening && (
                    <div className="summary-block">
                      <strong>{coachOpening.name}</strong>
                      <span className="muted">ECO {coachOpening.eco}</span>
                    </div>
                  )}
                  {coachFeatures && (
                    <div className="summary-block">
                      <strong>Position Brief</strong>
                      <div className="tag-row">
                        {(coachFeatures.global_themes || []).map((theme) => (
                          <span key={theme} className="tag">
                            {theme}
                          </span>
                        ))}
                      </div>
                      <div className="two-col">
                        <div>
                          <strong>White</strong>
                          <ul className="coach-lines">
                            <li>King: {coachFeatures.white?.king_safety}</li>
                            <li>Pawns: {(coachFeatures.white?.pawn_structure || []).join(", ")}</li>
                            <li>Activity: {coachFeatures.white?.piece_activity}</li>
                            <li>Space: {typeof coachFeatures.white?.space === "object" ? "balanced" : coachFeatures.white?.space}</li>
                          </ul>
                        </div>
                        <div>
                          <strong>Black</strong>
                          <ul className="coach-lines">
                            <li>King: {coachFeatures.black?.king_safety}</li>
                            <li>Pawns: {(coachFeatures.black?.pawn_structure || []).join(", ")}</li>
                            <li>Activity: {coachFeatures.black?.piece_activity}</li>
                            <li>Space: {typeof coachFeatures.black?.space === "object" ? "balanced" : coachFeatures.black?.space}</li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}
                  {coachPlans.length > 0 && (
                    <div className="stack">
                      {coachPlans.map((plan, idx) => (
                        <div key={`${plan.name}-${idx}`} className="summary-block">
                          <strong>{plan.name}</strong>
                          <p className="muted">{plan.idea}</p>
                          <div className="tag-row">
                            {(plan.example_moves || []).map((mv) => (
                              <span key={mv} className="tag">
                                {mv}
                              </span>
                            ))}
                          </div>
                          {plan.preconditions?.length > 0 && <p className="muted">Preconditions: {plan.preconditions.join(", ")}</p>}
                          {plan.risk && <p className="muted">Risk: {plan.risk}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="hint">Live coach updates will stream here after each move.</div>
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
