import { Chess } from "https://cdn.skypack.dev/chess.js@1.0.0";

const PROD_API_BASE = "https://chessica-1nh3.onrender.com";
const PROD_WS_BASE = "wss://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;
const WS_BASE = `${isLocal ? "ws://localhost:8000" : PROD_WS_BASE}/api/v1`;

const refs = {
  queueForm: document.getElementById("queueForm"),
  queueBtn: document.getElementById("queueBtn"),
  leaveBtn: document.getElementById("leaveBtn"),
  queueStatus: document.getElementById("queueStatus"),
  matchInfo: document.getElementById("matchInfo"),
  sessionIdDisplay: document.getElementById("sessionIdDisplay"),
  playerColorDisplay: document.getElementById("playerColorDisplay"),
  board: document.getElementById("onlineBoard"),
  moveList: document.getElementById("onlineMoveList"),
  messages: document.getElementById("onlineMessages"),
  sessionInput: document.getElementById("sessionInput"),
  loadSessionBtn: document.getElementById("loadSessionBtn"),
  resignBtn: document.getElementById("resignBtn"),
  drawBtn: document.getElementById("drawBtn"),
  abortBtn: document.getElementById("abortBtn"),
  whiteClock: document.getElementById("whiteClock"),
  blackClock: document.getElementById("blackClock"),
  whiteClockLabel: document.getElementById("whiteClockLabel"),
  blackClockLabel: document.getElementById("blackClockLabel"),
  whiteClockTile: document.getElementById("whiteClockTile"),
  blackClockTile: document.getElementById("blackClockTile"),
  whiteClockProgress: document.getElementById("whiteClockProgress"),
  blackClockProgress: document.getElementById("blackClockProgress"),
  moveEmptyState: document.getElementById("moveEmptyState"),
  messagesEmptyState: document.getElementById("messagesEmptyState"),
  boardOverlay: document.getElementById("boardOverlay"),
  boardOverlayText: document.getElementById("boardOverlayText"),
  connectionBanner: document.getElementById("connectionBanner"),
  moveHighlight: document.getElementById("onlineMoveHighlight"),
};

const state = {
  queueing: false,
  pollTimer: null,
  playerId: null,
  sessionId: null,
  playerColor: "white",
  initialMs: 300000,
  chess: new Chess(),
  movePairs: [],
  socket: null,
  heartbeatTimer: null,
  reconnectTimer: null,
  reconnectAttempts: 0,
  pendingMove: null,
};

function setStatus(text) {
  if (refs.queueStatus) refs.queueStatus.textContent = text;
}

function setMatchInfo(text) {
  if (refs.matchInfo) refs.matchInfo.textContent = text;
}

function setSessionId(text) {
  if (refs.sessionIdDisplay) refs.sessionIdDisplay.textContent = text || "";
}

function setPlayerColor(text) {
  if (refs.playerColorDisplay) refs.playerColorDisplay.textContent = text || "";
}

function hideEmptyState(el) {
  if (el) el.style.display = "none";
}

function showEmptyState(el) {
  if (el) el.style.display = "flex";
}

function showBoardOverlay(text) {
  if (!refs.boardOverlay || !refs.boardOverlayText) return;
  refs.boardOverlayText.textContent = text || "Loading…";
  refs.boardOverlay.hidden = false;
}

function hideBoardOverlay() {
  if (!refs.boardOverlay) return;
  refs.boardOverlay.hidden = true;
}

function setConnectionBanner(text, tone = "warn") {
  if (!refs.connectionBanner) return;
  refs.connectionBanner.textContent = text;
  refs.connectionBanner.hidden = false;
  refs.connectionBanner.classList.toggle("is-good", tone === "good");
  refs.connectionBanner.classList.toggle("is-bad", tone === "bad");
}

function hideConnectionBanner() {
  if (!refs.connectionBanner) return;
  refs.connectionBanner.hidden = true;
}

function updateClockLabels() {
  if (!refs.whiteClockLabel || !refs.blackClockLabel) return;
  if (state.playerColor === "white") {
    refs.whiteClockLabel.textContent = "You (White)";
    refs.blackClockLabel.textContent = "Opponent";
  } else {
    refs.whiteClockLabel.textContent = "Opponent";
    refs.blackClockLabel.textContent = "You (Black)";
  }
}

function logMessage(text) {
  if (!refs.messages) return;
  const li = document.createElement("li");
  li.textContent = text;
  refs.messages.prepend(li);
  hideEmptyState(refs.messagesEmptyState);
}

function formatMs(ms) {
  const clamped = Math.max(0, ms);
  if (clamped < 60000) {
    const seconds = Math.floor(clamped / 1000);
    const tenths = Math.floor((clamped % 1000) / 100);
    return `0:${seconds.toString().padStart(2, "0")}.${tenths}`;
  }
  const totalSeconds = Math.floor(clamped / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function updateClocks(clocks) {
  if (!clocks) return;
  if (!state.initialMs) {
    state.initialMs = Math.max(clocks.player_ms ?? 0, clocks.engine_ms ?? 0, 300000);
  }
  if (refs.whiteClock) refs.whiteClock.textContent = formatMs(clocks.player_ms ?? 0);
  if (refs.blackClock) refs.blackClock.textContent = formatMs(clocks.engine_ms ?? 0);
  setClockProgress("white", clocks.player_ms ?? 0);
  setClockProgress("black", clocks.engine_ms ?? 0);
}

function updateTurnIndicator() {
  const turn = state.chess.turn() === "w" ? "white" : "black";
  const status = turn === state.playerColor ? "Your turn" : "Opponent's turn";
  setStatus(`${status}. Queue: ${state.queueing ? "waiting" : "ready"}`);
  if (refs.whiteClockTile && refs.blackClockTile) {
    refs.whiteClockTile.classList.toggle("is-active", turn === "white");
    refs.blackClockTile.classList.toggle("is-active", turn === "black");
  }
}

function setClockProgress(color, remainingMs) {
  const progressEl = color === "white" ? refs.whiteClockProgress : refs.blackClockProgress;
  if (!progressEl) return;
  const base = state.initialMs || Math.max(remainingMs, 1);
  const ratio = Math.max(0, Math.min(1, remainingMs / base));
  progressEl.style.transform = `scaleX(${ratio})`;
}

function playMoveHighlight() {
  const highlight = refs.moveHighlight;
  if (!highlight || !refs.board) return;
  highlight.style.left = "0";
  highlight.style.top = "0";
  highlight.style.width = "100%";
  highlight.style.height = "100%";
  highlight.classList.add("visible");
  setTimeout(() => {
    highlight.classList.remove("visible");
  }, 200);
}

function applyOptimisticMove(uci) {
  if (state.pendingMove) return false;
  const prevFen = state.chess.fen();
  const move = state.chess.move({
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    promotion: uci.slice(4) || undefined,
  });
  if (!move) return false;
  playMoveSound(move.captured);
  state.pendingMove = {
    uci,
    prevFen,
    prevPairsLen: state.movePairs.length,
  };
  addSanMove(move.san, move.color);
  renderBoard();
  showBoardOverlay("Sending move…");
  return true;
}

function revertPendingMove() {
  if (!state.pendingMove) return;
  const { prevFen, prevPairsLen } = state.pendingMove;
  state.pendingMove = null;
  state.chess.load(prevFen);
  state.movePairs = state.movePairs.slice(0, prevPairsLen);
  renderMoveList();
  renderBoard();
  hideBoardOverlay();
}

function clearPendingMove() {
  state.pendingMove = null;
  hideBoardOverlay();
}

function playMoveSound(captured) {
  const freq = captured ? 520 : 760;
  playTone(freq, 0.12);
}

let audioCtx;
function playTone(frequency, duration) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "triangle";
    osc.frequency.value = frequency;
    gain.gain.value = 0.08;
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch {
    // ignore
  }
}

function renderBoard() {
  if (!refs.board) return;
  refs.board.setAttribute("position", state.chess.fen());
  refs.board.setAttribute("orientation", state.playerColor);
  updateTurnIndicator();
  hideMoveHighlight();
}

function resetMoveList() {
  state.movePairs = [];
  if (refs.moveList) refs.moveList.innerHTML = "";
  showEmptyState(refs.moveEmptyState);
}

function renderMoveList() {
  if (!refs.moveList) return;
  refs.moveList.innerHTML = "";
  if (!state.movePairs.length) {
    showEmptyState(refs.moveEmptyState);
    return;
  }
  hideEmptyState(refs.moveEmptyState);
  state.movePairs.forEach((pair) => {
    const li = document.createElement("li");
    li.textContent = `${pair.number}. ${pair.white || "..."} ${pair.black || "..."}`;
    refs.moveList.appendChild(li);
  });
}

function addSanMove(san, color) {
  if (!san) return;
  if (color === "w" || color === "white") {
    const number = state.movePairs.length + 1;
    state.movePairs.push({ number, white: san, black: null });
  } else {
    if (!state.movePairs.length) {
      state.movePairs.push({ number: 1, white: "...", black: san });
    } else {
      const last = state.movePairs[state.movePairs.length - 1];
      if (last.black) {
        state.movePairs.push({ number: state.movePairs.length + 1, white: "...", black: san });
      } else {
        last.black = san;
      }
    }
  }
  renderMoveList();
}

function applyUci(uci) {
  const move = state.chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci.slice(4) || undefined });
  if (move) addSanMove(move.san, move.color);
  renderBoard();
}

async function joinQueue(payload) {
  const res = await fetch(`${API_BASE}/multiplayer/queue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Queue failed (${res.status})`);
  }
  return res.json();
}

async function leaveQueue(playerId) {
  await fetch(`${API_BASE}/multiplayer/queue/${encodeURIComponent(playerId)}`, { method: "DELETE" });
}

async function pollStatus() {
  if (!state.playerId || !state.queueing) return;
  try {
    const res = await fetch(`${API_BASE}/multiplayer/queue/${encodeURIComponent(state.playerId)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === "matched") {
      handleMatched(data);
    } else if (data.status === "none") {
      state.queueing = false;
      setStatus("Not queued.");
      hideBoardOverlay();
    }
  } catch {
    // ignore
  }
}

function handleMatched(data) {
  state.queueing = false;
  clearInterval(state.pollTimer);
  state.sessionId = data.session_id;
  state.playerColor = data.player_color || "white";
  setStatus("Matched!");
  setMatchInfo(`Session ready. Your color: ${state.playerColor}`);
  setSessionId(`Session ID: ${state.sessionId}`);
  setPlayerColor(`Playing as ${state.playerColor}`);
  updateClockLabels();
  logMessage("Matched. Loading session...");
  hideBoardOverlay();
  loadSessionDetail();
}

function startPolling() {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(pollStatus, 2500);
}

async function loadSessionDetail(sessionId = null) {
  const sid = sessionId || state.sessionId;
  if (!sid) return;
  const res = await fetch(`${API_BASE}/sessions/${sid}`);
  if (!res.ok) {
    logMessage("Failed to load session.");
    return;
  }
  const detail = await res.json();
  state.sessionId = detail.session_id;
  state.playerColor = detail.player_white_id === state.playerId ? "white" : detail.player_black_id === state.playerId ? "black" : state.playerColor;
  state.initialMs = state.initialMs || Math.max(detail?.clocks?.player_ms ?? 0, detail?.clocks?.engine_ms ?? 0, 300000);
  state.pendingMove = null;
  state.chess.load(detail.fen);
  resetMoveList();
  (detail.moves || []).forEach((uci) => applyUci(uci));
  setSessionId(`Session ID: ${state.sessionId}`);
  setPlayerColor(`Playing as ${state.playerColor}`);
  updateClockLabels();
  setMatchInfo(`Opponent: ${state.player_white_id === state.playerId ? detail.player_black_id : detail.player_white_id || "?"}`);
  renderBoard();
  updateClocks(detail.clocks);
  hideBoardOverlay();
  connectStream();
}

async function submitMove(uci, wasOptimistic = false) {
  if (!state.sessionId || !state.playerId) {
    logMessage("Join a match first.");
    return;
  }
  if (!wasOptimistic) {
    showBoardOverlay("Sending move…");
  }
  const payload = {
    uci,
    player_id: state.playerId,
    client_ts: new Date().toISOString(),
  };
  const res = await fetch(`${API_BASE}/multiplayer/sessions/${state.sessionId}/moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    logMessage(`Move failed (${res.status})`);
    if (wasOptimistic) {
      revertPendingMove();
    } else {
      hideBoardOverlay();
    }
    return;
  }
  const data = await res.json();
  logMessage(`Played ${uci}, eval ${data.eval_cp}`);
  if (data.clocks) {
    updateClocks(data.clocks);
  }
  clearPendingMove();
}

function connectStream() {
  if (!state.sessionId) return;
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  if (state.socket) {
    try {
      state.socket.close();
    } catch (_) {
      // ignore
    }
  }
  const socket = new WebSocket(`${WS_BASE}/sessions/${state.sessionId}/stream`);
  state.socket = socket;
  socket.onopen = () => {
    state.reconnectAttempts = 0;
    logMessage("Stream connected.");
    hideConnectionBanner();
    startHeartbeat();
  };
  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "player_move") {
        const moveUci = data.payload?.uci;
        if (data.payload?.clocks) {
            updateClocks(data.payload.clocks);
        }
        if (moveUci) {
          const moveWasPending = state.pendingMove && state.pendingMove.uci === moveUci;
          if (state.pendingMove && state.pendingMove.uci === moveUci) {
            clearPendingMove();
          }
          // Avoid double-applying moves
          const history = state.chess.history({ verbose: true });
          const last = history[history.length - 1];
          if (last && last.from + last.to + (last.promotion || "") === moveUci) {
            return;
          }
          const move = state.chess.move({
            from: moveUci.slice(0, 2),
            to: moveUci.slice(2, 4),
            promotion: moveUci.slice(4) || undefined,
          });
          if (move) {
            addSanMove(move.san, move.color);
            renderBoard();
            playMoveSound(move?.captured);
            if (!moveWasPending) {
              playMoveHighlight();
            }
          }
        }
      }
      if (data.type === "game_over") {
        logMessage(data.payload?.message || "Game over");
      }
      if (data.type === "status") {
        logMessage(data.payload || "");
      }
    } catch {
      // ignore
    }
  };
  socket.onerror = () => logMessage("Stream error.");
  socket.onclose = () => {
    logMessage("Stream closed.");
    setConnectionBanner("Stream disconnected. Reconnecting…", "warn");
    stopHeartbeat();
    scheduleReconnect();
  };
}

function stopHeartbeat() {
  if (state.heartbeatTimer) {
    clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
  }
}

function startHeartbeat() {
  stopHeartbeat();
  state.heartbeatTimer = setInterval(() => {
    if (state.socket?.readyState === WebSocket.OPEN) {
      try {
        state.socket.send(JSON.stringify({ type: "ping", ts: Date.now() }));
      } catch {
        // ignore send failure; reconnect will pick it up
      }
    }
  }, 15000);
}

function scheduleReconnect() {
  if (!state.sessionId) return;
  if (state.reconnectTimer) return;
  const attempt = state.reconnectAttempts || 0;
  const delay = Math.min(8000, 500 * 2 ** attempt);
  state.reconnectAttempts = attempt + 1;
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    connectStream();
  }, delay);
}

// Drag/drop handlers
if (refs.board) {
  refs.board.addEventListener("drag-start", (event) => {
    const pieceColor = event.detail.piece?.startsWith("w") ? "white" : "black";
    const turn = state.chess.turn() === "w" ? "white" : "black";
    if (pieceColor !== state.playerColor || turn !== state.playerColor) {
      event.preventDefault();
    }
  });

  refs.board.addEventListener("drop", async (event) => {
    const { source, target, setAction } = event.detail;
    if (state.pendingMove) {
      logMessage("Wait for the previous move to send.");
      setAction("snapback");
      return;
    }
    const moves = state.chess.moves({ verbose: true }).filter((m) => m.from === source && m.to === target);
    if (!moves.length) {
      setAction("snapback");
      return;
    }
    const move = moves[0];
    const uci = move.from + move.to + (move.promotion || "");
    try {
      const applied = applyOptimisticMove(uci);
      if (!applied) {
        setAction("snapback");
        return;
      }
      await submitMove(uci, true);
      setAction("move");
    } catch {
      revertPendingMove();
      setAction("snapback");
    }
  });
}

// Queue handlers
if (refs.queueForm) {
  refs.queueForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const player_id = (form.get("player_id") || "").toString().trim();
    const color = form.get("color") || "auto";
    const initial_ms = Number(form.get("initial_ms") || 300000);
    const increment_ms = Number(form.get("increment_ms") || 2000);
    if (!player_id) {
      setStatus("Player ID required.");
      return;
    }
    state.playerId = player_id;
    state.initialMs = initial_ms || state.initialMs;
    setStatus("Joining queue...");
    showBoardOverlay("Matching…");
    try {
      const data = await joinQueue({
        player_id,
        color,
        time_control: { initial_ms, increment_ms },
      });
      if (data.status === "matched") {
        handleMatched(data);
      } else {
        state.queueing = true;
        setStatus("Queued. Waiting for opponent...");
        setMatchInfo("Searching...");
        startPolling();
      }
    } catch (error) {
      setStatus(error.message || "Failed to join queue.");
      hideBoardOverlay();
    }
  });
}

if (refs.leaveBtn) {
  refs.leaveBtn.addEventListener("click", async () => {
    if (!state.playerId) {
      setStatus("Not queued.");
      return;
    }
    try {
      await leaveQueue(state.playerId);
      state.queueing = false;
      clearInterval(state.pollTimer);
      setStatus("Left queue.");
      setMatchInfo("No match yet.");
      setSessionId("");
      setPlayerColor("");
      state.chess.reset();
      resetMoveList();
      renderBoard();
      hideBoardOverlay();
    } catch {
      setStatus("Unable to leave queue.");
    }
  });
}

if (refs.loadSessionBtn) {
  refs.loadSessionBtn.addEventListener("click", async () => {
    const sid = refs.sessionInput?.value?.trim();
    if (!sid) return;
    state.sessionId = sid;
    await loadSessionDetail(sid);
  });
}

if (refs.resignBtn) {
  refs.resignBtn.addEventListener("click", async () => {
    if (!state.sessionId) {
      logMessage("No session.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/multiplayer/sessions/${state.sessionId}/resign`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        logMessage(data.message || "Resigned.");
      } else {
        logMessage("Resign failed.");
      }
    } catch {
      logMessage("Resign failed.");
    }
  });
}

async function simplePost(path, successMsg, failureMsg) {
  try {
    const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      logMessage(data.message || successMsg);
    } else {
      logMessage(failureMsg);
    }
  } catch {
    logMessage(failureMsg);
  }
}

if (refs.drawBtn) {
  refs.drawBtn.addEventListener("click", async () => {
    if (!state.sessionId) {
      logMessage("No session.");
      return;
    }
    await simplePost(`/multiplayer/sessions/${state.sessionId}/draw`, "Draw offered.", "Draw failed.");
  });
}

if (refs.abortBtn) {
  refs.abortBtn.addEventListener("click", async () => {
    if (!state.sessionId) {
      logMessage("No session.");
      return;
    }
    await simplePost(`/multiplayer/sessions/${state.sessionId}/abort`, "Game aborted.", "Abort failed.");
  });
}

renderBoard();
resetMoveList();
