import { Chess } from "https://cdn.skypack.dev/chess.js@1.0.0";

const PROD_API_BASE = "https://chessica-1nh3.onrender.com";
const PROD_WS_BASE = "wss://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;
const WS_BASE = `${isLocal ? "ws://localhost:8000" : PROD_WS_BASE}/api/v1`;
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const state = {
  sessionId: null,
  sessionDetail: null,
  socket: null,
  movePairs: [],
  chess: new Chess(),
  playerColor: "white",
  gameOver: false,
};

const refs = {
  board: document.getElementById("board"),
  moveList: document.getElementById("moveList"),
  profileOutput: document.getElementById("profileOutput"),
  explanationSummary: document.getElementById("explanationSummary"),
  explanationDetails: document.getElementById("explanationDetails"),
  sessionStatus: document.getElementById("sessionStatus"),
  streamOutput: document.getElementById("streamOutput"),
  eventLog: document.getElementById("eventLog"),
  analyticsSummary: document.getElementById("analyticsSummary"),
  analyticsEvents: document.getElementById("analyticsEvents"),
  refreshAnalyticsBtn: document.getElementById("refreshAnalyticsBtn"),
  moveForm: document.getElementById("moveForm"),
  engineMoveBtn: document.getElementById("engineMoveBtn"),
  difficultySelect: document.getElementById("difficultySelect"),
  difficultyNote: document.getElementById("difficultyNote"),
};
refs.moveInput = refs.moveForm.elements.uci;
refs.moveSubmitBtn = refs.moveForm.querySelector('button[type="submit"]');

function log(message) {
  const timestamp = new Date().toLocaleTimeString();
  refs.eventLog.textContent = `[${timestamp}] ${message}\n${refs.eventLog.textContent}`;
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
  updateMoveControls();
}

function updateMoveControls() {
  const yourTurn = isPlayersTurn();
  const disableAll = state.gameOver || !state.sessionId;
  if (refs.moveSubmitBtn) {
    refs.moveSubmitBtn.disabled = disableAll || !yourTurn;
  }
  if (refs.moveInput) {
    refs.moveInput.disabled = disableAll || !yourTurn;
    refs.moveInput.placeholder = state.gameOver
      ? "Game over"
      : yourTurn
        ? "e2e4"
        : "Waiting for engine…";
  }
  if (refs.engineMoveBtn) {
    refs.engineMoveBtn.disabled = disableAll || yourTurn;
  }
}

function isPlayersTurn() {
  const desired = state.playerColor === "white" ? "w" : "b";
  return state.chess.turn() === desired;
}

function initTabs() {
  const container = document.querySelector(".info-card");
  if (!container) return;
  const buttons = container.querySelectorAll("[data-tab-target]");
  const panels = container.querySelectorAll("[data-tab-panel]");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.tabTarget;
      buttons.forEach((btn) => btn.classList.toggle("active", btn === button));
      panels.forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.tabPanel === target);
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
  refs.sessionStatus.textContent = `Session ${session.session_id} · Engine plays ${
    session.engine_color
  } · ${capitalize(session.difficulty)} (~${session.engine_rating} Elo, depth ${session.engine_depth})`;
  log(`Created session ${session.session_id}`);
  await loadSessionDetail();
  connectStream();
  await fetchAnalytics(true);
}

async function loadSessionDetail() {
  if (!state.sessionId) return;
  const res = await fetch(`${API_BASE}/sessions/${state.sessionId}`);
  if (!res.ok) throw new Error("Failed to load session detail");
  const detail = await res.json();
  state.sessionDetail = detail;
  state.movePairs = [];
  state.chess.load(detail.fen);
  refs.sessionStatus.textContent = `Session ${detail.session_id} · Engine plays ${detail.engine_color} · ${capitalize(
    detail.difficulty,
  )} (~${detail.engine_rating} Elo, depth ${detail.engine_depth})`;
  renderBoard();
  refs.profileOutput.textContent = JSON.stringify(detail.opponent_profile, null, 2);
  refs.moveList.innerHTML = "";
  detail.moves.forEach((move, idx) => appendMoveListItem(idx + 1, move));
}

async function fetchAnalytics(autoRefresh = false) {
  if (!state.sessionId) {
    refs.analyticsSummary.textContent = "Start a session to view analytics.";
    refs.analyticsEvents.innerHTML = "";
    return;
  }
  refs.analyticsSummary.textContent = autoRefresh ? "Updating analytics…" : "Refreshing analytics…";
  try {
    const res = await fetch(`${API_BASE}/analytics/sessions/${state.sessionId}/events`);
    if (!res.ok) {
      throw new Error(`Analytics request failed (${res.status})`);
    }
    const data = await res.json();
    const counts = data.summary.counts_by_type;
    const parts = Object.entries(counts)
      .map(([key, value]) => `${key}: ${value}`)
      .join(" · ");
    refs.analyticsSummary.textContent = `Events: ${data.summary.total_events} (${parts || "no data"})`;
    refs.analyticsEvents.innerHTML = "";
    data.events.slice(-10).forEach((event) => {
      const li = document.createElement("li");
      li.textContent = `[${new Date(event.created_at).toLocaleTimeString()}] ${event.event_type}: ${formatEventPayload(
        event,
      )}`;
      refs.analyticsEvents.prepend(li);
    });
  } catch (error) {
    refs.analyticsSummary.textContent = error.message;
    refs.analyticsEvents.innerHTML = "";
  }
}

function formatEventPayload(event) {
  if (event.payload?.uci) {
    return `move ${event.payload.uci}`;
  }
  if (event.event_type === "session_resigned") {
    return "session ended";
  }
  return JSON.stringify(event.payload);
}

async function submitMove(uciValue, { bypassTurnCheck = false } = {}) {
  if (!state.sessionId) {
    alert("Create a session first.");
    return;
  }
  if (state.gameOver) {
    alert("Game over. Start a new session.");
    return;
  }
  if (uciValue && !bypassTurnCheck && !isPlayersTurn()) {
    alert("Wait for the engine to move first.");
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
    alert("Move failed; see log for details.");
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
  refs.profileOutput.textContent = JSON.stringify(response.opponent_profile, null, 2);
  refs.explanationSummary.textContent = response.explanation.summary;
  refs.explanationDetails.innerHTML = `
    <li>Objective cost: ${response.explanation.objective_cost_cp} cp</li>
    <li>Alt best move: ${response.explanation.alt_best_move} (${response.explanation.alt_eval_cp} cp)</li>
    <li>Exploit confidence: ${(response.exploit_confidence * 100).toFixed(1)}%</li>
  `;

  if (uciValue) {
    const pairText = response.engine_move ? `${uciValue} / ${response.engine_move}` : `${uciValue}`;
    appendMoveListItem(state.movePairs.length + 1, pairText);
  } else {
    const pairText = response.engine_move ? `(engine start) / ${response.engine_move}` : "(engine start)";
    appendMoveListItem(state.movePairs.length + 1, pairText);
  }
  if (response.engine_move) {
    log(`Engine replied with ${response.engine_move} (eval ${response.engine_eval_cp} cp)`);
  } else if (response.result) {
    log(response.message || `Game over (${response.result}).`);
  }
  await fetchAnalytics(true);
  if (response.result) {
    state.gameOver = true;
    refs.sessionStatus.textContent = response.message || `Game over (${response.result})`;
  }
  updateMoveControls();
  return response;
}

function appendMoveListItem(idx, text) {
  const li = document.createElement("li");
  li.textContent = `${idx}. ${text}`;
  refs.moveList.appendChild(li);
  state.movePairs.push(text);
}

function connectStream() {
  if (!state.sessionId) return;
  if (state.socket) {
    state.socket.close();
  }
  const socket = new WebSocket(`${WS_BASE}/sessions/${state.sessionId}/stream`);
  state.socket = socket;
  socket.onopen = () => {
    refs.streamOutput.textContent = "Stream connected.";
  };
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "game_over") {
        state.gameOver = true;
        const message = data.payload?.message || "Game over.";
        refs.sessionStatus.textContent = message;
        log(message);
        updateMoveControls();
      }
      refs.streamOutput.textContent = `${event.data}\n${refs.streamOutput.textContent}`;
    } catch (error) {
      refs.streamOutput.textContent = `${event.data}\n${refs.streamOutput.textContent}`;
    }
  };
  socket.onclose = () => {
    refs.streamOutput.textContent = "Stream closed.";
  };
}

initTabs();

document.getElementById("sessionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = {
    variant: "standard",
    color: form.get("color"),
    exploit_mode: form.get("exploit_mode"),
    difficulty: form.get("difficulty"),
    time_control: {
      initial_ms: Number(form.get("initial")) * 1000,
      increment_ms: Number(form.get("increment")) * 1000,
    },
  };
  try {
    await createSession(payload);
  } catch (error) {
    log(error.message);
    alert("Failed to create session. Check backend logs.");
  }
});

refs.moveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const inputValue = refs.moveInput.value.trim();
  if (!inputValue) {
    alert("Enter a move in UCI format (e.g., e2e4).");
    return;
  }
  try {
    await submitMove(inputValue);
    refs.moveInput.value = "";
  } catch {
    // handled in submitMove
  }
});

refs.engineMoveBtn.addEventListener("click", async () => {
  if (isPlayersTurn()) {
    alert("It's your move.");
    return;
  }
  try {
    await submitMove(null, { bypassTurnCheck: true });
  } catch {
    // handled in submitMove
  }
});

refs.refreshAnalyticsBtn.addEventListener("click", () => {
  fetchAnalytics(false);
});

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
