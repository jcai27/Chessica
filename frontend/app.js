import { Chess } from "https://cdn.skypack.dev/chess.js@1.0.0";

const PROD_API_BASE = "https://chessica-1nh3.onrender.com";
const PROD_WS_BASE = "wss://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;
const WS_BASE = `${isLocal ? "ws://localhost:8000" : PROD_WS_BASE}/api/v1`;
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const DEFAULT_TIME_CONTROL = {
  initial_ms: 300000,
  increment_ms: 2000,
};

const state = {
  sessionId: null,
  sessionDetail: null,
  socket: null,
  movePairs: [],
  chess: new Chess(),
  notationTracker: new Chess(),
  playerColor: "white",
  gameOver: false,
};

const refs = {
  board: document.getElementById("board"),
  moveList: document.getElementById("moveList"),
  insightSummary: document.getElementById("insightSummary"),
  insightDetails: document.getElementById("insightDetails"),
  evalScore: document.getElementById("evalScore"),
  evalDescriptor: document.getElementById("evalDescriptor"),
  positionDescriptor: document.getElementById("positionDescriptor"),
  themeTags: document.getElementById("themeTags"),
  analysisMoves: document.getElementById("analysisMoves"),
  sessionStatus: document.getElementById("sessionStatus"),
  refreshInsightBtn: document.getElementById("refreshInsightBtn"),
  tacticalValue: document.getElementById("tacticalValue"),
  tacticalBar: document.getElementById("tacticalBar"),
  positionalValue: document.getElementById("positionalValue"),
  riskValue: document.getElementById("riskValue"),
  riskBar: document.getElementById("riskBar"),
  difficultySelect: document.getElementById("difficultySelect"),
  difficultyNote: document.getElementById("difficultyNote"),
};

function log(message) {
  console.info(`[Chessica] ${message}`);
}

function updateDifficultyNote() {
  if (!refs.difficultySelect || !refs.difficultyNote) return;
  const option = refs.difficultySelect.selectedOptions[0];
  if (!option) return;
  const rating = option.dataset.rating ?? "";
  const depth = option.dataset.depth ?? "";
  refs.difficultyNote.textContent = `${option.textContent} (depth ${depth || "?"})`;  
}

function renderBoard() {
  refs.board.setAttribute("orientation", state.playerColor);
  refs.board.setAttribute("position", state.chess.fen());
  updatePositionDescriptor();
}

function isPlayersTurn() {
  const desired = state.playerColor === "white" ? "w" : "b";
  return state.chess.turn() === desired;
}

function formatEval(cp) {
  if (typeof cp !== "number") return "—";
  const score = (cp / 100).toFixed(2);
  return cp >= 0 ? `+${score}` : score;
}

function describeEval(cp) {
  if (typeof cp !== "number") return "No evaluation yet";
  const abs = Math.abs(cp);
  if (abs < 35) return "Balanced tension";
  if (abs < 150) return cp > 0 ? "White edge" : "Black edge";
  if (abs < 300) return cp > 0 ? "White pressing" : "Black pressing";
  return cp > 0 ? "White winning" : "Black winning";
}

function describeMaterialBalance() {
  const board = state.chess.board();
  const values = { p: 1, n: 3, b: 3.25, r: 5, q: 9 };
  let score = 0;
  board.flat().forEach((piece) => {
    if (!piece) return;
    const value = values[piece.type] || 0;
    score += piece.color === "w" ? value : -value;
  });
  if (Math.abs(score) < 0.25) return "Material level.";
  const side = score > 0 ? "White" : "Black";
  return `${side} is up roughly ${Math.abs(score).toFixed(1)} points of material.`;
}

function updatePositionDescriptor() {
  if (!refs.positionDescriptor) return;
  if (!state.sessionId) {
    refs.positionDescriptor.textContent = "Start a session to generate a position briefing.";
    return;
  }
  const fenParts = state.chess.fen().split(" ");
  const fullMoves = Number(fenParts[5]) || 1;
  const turn = state.chess.turn() === "w" ? "White" : "Black";
  refs.positionDescriptor.textContent = `Move ${fullMoves}, ${turn} to move. ${describeMaterialBalance()}`;
}

function resetMoveHistory() {
  state.movePairs = [];
  state.notationTracker = new Chess();
  renderMoveList();
}

function rebuildNotationFromMoves(moves = []) {
  resetMoveHistory();
  moves.forEach((uci) => applyUciToNotation(uci));
}

function renderMoveList() {
  if (!refs.moveList) return;
  refs.moveList.innerHTML = "";
  if (!state.movePairs.length) {
    const placeholder = document.createElement("li");
    placeholder.textContent = "No moves recorded.";
    refs.moveList.appendChild(placeholder);
    return;
  }
  state.movePairs.forEach((pair) => {
    const li = document.createElement("li");
    const blackMove = pair.black ? pair.black : "…";
    li.textContent = `${pair.number}. ${pair.white || "…"} ${blackMove}`;
    refs.moveList.appendChild(li);
  });
}

function applyUciToNotation(uci) {
  if (!uci || !state.notationTracker) return null;
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const promotion = uci.length > 4 ? uci.slice(4) : undefined;
  const move = state.notationTracker.move({ from, to, promotion });
  if (!move) return null;
  addSanMove(move.san, move.color === "w" ? "white" : "black");
  return move.san;
}

function addSanMove(san, color) {
  if (!san) return;
  if (color === "white") {
    const number = state.movePairs.length + 1;
    state.movePairs.push({ number, white: san, black: null });
  } else {
    if (state.movePairs.length === 0) {
      state.movePairs.push({ number: 1, white: "…", black: san });
    } else {
      const last = state.movePairs[state.movePairs.length - 1];
      if (last.black) {
        state.movePairs.push({ number: state.movePairs.length + 1, white: "…", black: san });
      } else {
        last.black = san;
      }
    }
  }
  renderMoveList();
}

function resetInsights(message = "No moves yet.") {
  if (refs.insightSummary) {
    refs.insightSummary.textContent = message;
  }
  if (refs.insightDetails) {
    refs.insightDetails.innerHTML = "<li>Submit a move to see evaluation metrics.</li>";
  }
  if (refs.evalScore) {
    refs.evalScore.textContent = "+0.00";
  }
  if (refs.evalDescriptor) {
    refs.evalDescriptor.textContent = "Awaiting session";
  }
  renderThemeTags([]);
  renderAnalysisMoves([]);
  updatePositionDescriptor();
  updateTendencies(null);
}

function updateInsightFromResponse(response) {
  if (!response || !refs.insightSummary) return;
  refs.insightSummary.textContent = response.explanation.summary;
  const latestInsight = response.latest_insight;
  const verdictBullet = latestInsight
    ? `<li>Move verdict: ${capitalize(latestInsight.verdict)} (${formatEval(latestInsight.delta_cp)})</li>`
    : "";
  const commentaryBullet = latestInsight ? `<li>${latestInsight.commentary}</li>` : "";
  const themeBullet =
    latestInsight && latestInsight.themes?.length
      ? `<li>Triggered themes: ${latestInsight.themes.join(", ")}</li>`
      : "";
  if (refs.insightDetails) {
    refs.insightDetails.innerHTML = `
      <li>Objective cost: ${response.explanation.objective_cost_cp} cp</li>
      <li>Alt best move: ${response.explanation.alt_best_move} (${formatEval(response.explanation.alt_eval_cp)})</li>
      <li>Exploit confidence: ${(response.exploit_confidence * 100).toFixed(1)}%</li>
      ${verdictBullet}
      ${commentaryBullet}
      ${themeBullet}
    `;
  }
  if (refs.evalScore) {
    refs.evalScore.textContent = formatEval(response.engine_eval_cp);
  }
  if (refs.evalDescriptor) {
    refs.evalDescriptor.textContent = describeEval(response.engine_eval_cp);
  }
  updatePositionDescriptor();
}

function renderThemeTags(themes = []) {
  if (!refs.themeTags) return;
  if (!themes.length) {
    refs.themeTags.textContent = "No motifs captured yet.";
    return;
  }
  refs.themeTags.innerHTML = "";
  themes.forEach((theme) => {
    const pill = document.createElement("span");
    pill.textContent = theme;
    refs.themeTags.appendChild(pill);
  });
}

function renderAnalysisMoves(moves = []) {
  if (!refs.analysisMoves) return;
  if (!moves.length) {
    refs.analysisMoves.innerHTML = "<li>No annotated moves yet.</li>";
    return;
  }
  refs.analysisMoves.innerHTML = "";
  moves.forEach((move) => {
    const li = document.createElement("li");
    const label = document.createElement("strong");
    label.textContent = `${move.ply}. ${move.player_move || "…"} → ${move.engine_reply || "…"}`;
    li.appendChild(label);

    const meta = document.createElement("span");
    meta.textContent = `Eval ${formatEval(move.objective_eval_cp)} • Exploit +${move.exploit_gain_cp} cp`;
    li.appendChild(meta);

    const motifs = document.createElement("span");
    motifs.textContent = move.motifs?.length ? `Motifs: ${move.motifs.join(", ")}` : "Motifs: n/a";
    li.appendChild(motifs);

    if (move.explanation) {
      const detail = document.createElement("p");
      detail.textContent = move.explanation;
      li.appendChild(detail);
    }
    refs.analysisMoves.appendChild(li);
  });
}

function updateTendencies(profile) {
  const tactical = Math.round((profile?.style?.tactical ?? 0) * 100);
  const positional = 100 - tactical;
  const risk = Math.round((profile?.style?.risk ?? 0) * 100);
  if (refs.tacticalValue) {
    refs.tacticalValue.textContent = `${tactical}%`;
  }
  if (refs.positionalValue) {
    refs.positionalValue.textContent = `Positional: ${positional}%`;
  }
  if (refs.tacticalBar) {
    refs.tacticalBar.style.width = `${tactical}%`;
  }
  if (refs.riskValue) {
    refs.riskValue.textContent = `${risk}%`;
  }
  if (refs.riskBar) {
    refs.riskBar.style.width = `${risk}%`;
  }
}

async function ensureEngineOpensIfNeeded() {
  if (!state.sessionId || state.gameOver) return;
  if (!isPlayersTurn()) {
    try {
      await submitMove(null, { bypassTurnCheck: true, suppressAlerts: true });
    } catch (error) {
      log(error.message);
    }
  }
}

function initInsightTabs() {
  const tabs = document.querySelectorAll(".insight-tab");
  const panes = document.querySelectorAll(".insight-pane");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.insightTab;
      tabs.forEach((btn) => btn.classList.toggle("active", btn === tab));
      panes.forEach((pane) => {
        pane.classList.toggle("active", pane.dataset.insightPanel === target);
      });
    });
  });
}

async function createSession(payload) {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to create session (${res.status})`);
  }
  const session = await res.json();
  state.sessionId = session.session_id;
  state.playerColor = session.player_color;
  state.gameOver = false;
  state.chess.load(START_FEN);
  resetInsights();
  resetMoveHistory();
  refs.sessionStatus.textContent = `Session ${session.session_id} · Engine plays ${
    session.engine_color
  } · ${capitalize(session.difficulty)} (~${session.engine_rating} Elo, depth ${session.engine_depth})`;
  log(`Created session ${session.session_id}`);
  await loadSessionDetail();
  connectStream();
  await fetchPositionAnalysis(true);
}

async function loadSessionDetail() {
  if (!state.sessionId) return;
  const res = await fetch(`${API_BASE}/sessions/${state.sessionId}`);
  if (!res.ok) throw new Error("Failed to load session detail");
  const detail = await res.json();
  state.sessionDetail = detail;
  state.chess.load(detail.fen);
  resetInsights(detail.moves.length ? "Resume play to update insights." : "No moves yet.");
  refs.sessionStatus.textContent = `Session ${detail.session_id} · Engine plays ${detail.engine_color} · ${capitalize(
    detail.difficulty,
  )} (~${detail.engine_rating} Elo, depth ${detail.engine_depth})`;
  renderBoard();
  updateTendencies(detail.opponent_profile);
  rebuildNotationFromMoves(detail.moves || []);
  await ensureEngineOpensIfNeeded();
}

async function fetchPositionAnalysis(autoRefresh = false) {
  if (!state.sessionId) {
    renderThemeTags([]);
    renderAnalysisMoves([]);
    return;
  }
  if (!autoRefresh && refs.refreshInsightBtn) {
    refs.refreshInsightBtn.disabled = true;
  }
  try {
    const res = await fetch(`${API_BASE}/sessions/${state.sessionId}/analysis`);
    if (!res.ok) {
      throw new Error(`Insight request failed (${res.status})`);
    }
    const data = await res.json();
    renderThemeTags(data.summary?.themes ?? []);
    renderAnalysisMoves(data.moves ?? []);
  } catch (error) {
    if (refs.themeTags) {
      refs.themeTags.textContent = error.message;
    }
    if (refs.analysisMoves) {
      refs.analysisMoves.innerHTML = "";
    }
  } finally {
    if (refs.refreshInsightBtn) {
      refs.refreshInsightBtn.disabled = false;
    }
  }
}

async function submitMove(uciValue, { bypassTurnCheck = false, suppressAlerts = false } = {}) {
  if (!state.sessionId) {
    if (!suppressAlerts) alert("Create a session first.");
    return;
  }
  if (state.gameOver) {
    if (!suppressAlerts) alert("Game over. Start a new session.");
    return;
  }
  if (uciValue && !bypassTurnCheck && !isPlayersTurn()) {
    if (!suppressAlerts) alert("Wait for the engine to move first.");
    return;
  }

  const clocks = state.sessionDetail?.clocks ?? { player_ms: 300000, engine_ms: 300000 };
  if (state.sessionDetail) {
    state.sessionDetail.clocks = clocks;
  }
  const payload = {
    uci: uciValue || null,
    client_ts: new Date().toISOString(),
    clock: clocks,
    telemetry: {
      ui_version: "prototype",
    },
  };

  const previousFen = state.chess.fen();
  const res = await fetch(`${API_BASE}/sessions/${state.sessionId}/moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    log(`Move rejected: ${errorText}`);
    state.chess.load(previousFen);
    renderBoard();
    if (!suppressAlerts) alert("Move failed; see log for details.");
    throw new Error(errorText);
  }

  const response = await res.json();
  state.sessionDetail = {
    ...state.sessionDetail,
    fen: response.game_state.fen,
    opponent_profile: response.opponent_profile,
  };
  state.chess.load(response.game_state.fen);
  renderBoard();
  updateTendencies(response.opponent_profile);
  updateInsightFromResponse(response);

  if (uciValue) {
    applyUciToNotation(uciValue);
  }
  if (response.engine_move) {
    log(`Engine replied with ${response.engine_move} (eval ${response.engine_eval_cp} cp)`);
    applyUciToNotation(response.engine_move);
  } else if (response.result) {
    log(response.message || `Game over (${response.result}).`);
  }
  await fetchPositionAnalysis(true);
  if (response.result) {
    state.gameOver = true;
    refs.sessionStatus.textContent = response.message || `Game over (${response.result})`;
  }
  return response;
}

function connectStream() {
  if (!state.sessionId) return;
  if (state.socket) {
    state.socket.close();
  }
  const socket = new WebSocket(`${WS_BASE}/sessions/${state.sessionId}/stream`);
  state.socket = socket;
  socket.onopen = () => {
    log("Stream connected.");
  };
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "game_over") {
        state.gameOver = true;
        const message = data.payload?.message || "Game over.";
        refs.sessionStatus.textContent = message;
        log(message);
      }
    } catch (error) {
      log(`Stream message: ${event.data}`);
    }
  };
  socket.onclose = () => {
    log("Stream closed.");
  };
}

initInsightTabs();

document.getElementById("sessionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    variant: "standard",
    color: form.get("color"),
    exploit_mode: form.get("exploit_mode"),
    difficulty: form.get("difficulty"),
    time_control: DEFAULT_TIME_CONTROL,
  };
  try {
    await createSession(payload);
  } catch (error) {
    log(error.message);
    alert("Failed to create session. Check backend logs.");
  }
});

if (refs.refreshInsightBtn) {
  refs.refreshInsightBtn.addEventListener("click", () => {
    fetchPositionAnalysis(false);
  });
}

if (refs.difficultySelect) {
  refs.difficultySelect.addEventListener("change", updateDifficultyNote);
  updateDifficultyNote();
}

refs.board.addEventListener("drag-start", (event) => {
  if (!state.sessionId || state.gameOver || !isPlayersTurn()) {
    event.preventDefault();
    return;
  }
  const pieceColor = event.detail.piece?.startsWith("w") ? "white" : "black";
  if (pieceColor !== state.playerColor) {
    event.preventDefault();
  }
});

refs.board.addEventListener("drop", async (event) => {
  const { source, target, setAction } = event.detail;
  if (!state.sessionId || state.gameOver || !isPlayersTurn()) {
    setAction("snapback");
    return;
  }
  const move = state.chess.moves({ verbose: true }).find((m) => m.from === source && m.to === target);
  if (!move) {
    setAction("snapback");
    return;
  }
  const uci = move.from + move.to + (move.promotion ? move.promotion : "");
  try {
    await submitMove(uci);
    setAction("move");
  } catch {
    setAction("snapback");
  }
});

function capitalize(value) {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

renderBoard();
resetInsights();
resetMoveHistory();
