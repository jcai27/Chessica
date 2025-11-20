import { Chess } from "https://cdn.skypack.dev/chess.js@1.0.0";

const PROD_API_BASE = "https://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;

const refs = {
  form: document.getElementById("replayForm"),
  sessionInput: document.getElementById("replaySessionInput"),
  status: document.getElementById("replayStatus"),
  board: document.getElementById("replayBoard"),
  meta: document.getElementById("replayMeta"),
  progress: document.getElementById("replayProgress"),
  moves: document.getElementById("replayMoves"),
  copyBtn: document.getElementById("replayCopyBtn"),
  downloadBtn: document.getElementById("replayDownloadBtn"),
};

const state = {
  sessionId: null,
  replay: null,
  chess: new Chess(),
  currentPly: 0,
  lastHighlight: [],
};

function log(message) {
  console.info(`[Replay] ${message}`);
}

function shareUrl() {
  if (!state.sessionId) return "";
  const url = new URL(window.location.href);
  return `${url.origin}${url.pathname}?session=${state.sessionId}`;
}

function setStatus(text) {
  if (refs.status) refs.status.textContent = text;
}

function clearHighlights() {
  const root = refs.board?.shadowRoot;
  if (!root) return;
  state.lastHighlight.forEach((sq) => {
    const el = root.querySelector(`[data-square="${sq}"]`);
    if (el) {
      el.style.boxShadow = "";
      el.style.filter = "";
    }
  });
  state.lastHighlight = [];
}

function highlightMove(uci) {
  clearHighlights();
  if (!uci) return;
  const squares = [uci.slice(0, 2), uci.slice(2, 4)];
  const root = refs.board?.shadowRoot;
  if (!root) return;
  squares.forEach((sq) => {
    const el = root.querySelector(`[data-square="${sq}"]`);
    if (el) {
      el.style.boxShadow = "inset 0 0 0 3px rgba(52, 211, 153, 0.6)";
      el.style.filter = "brightness(1.05)";
    }
  });
  state.lastHighlight = squares;
}

function applyUci(chess, uci) {
  if (!uci) return null;
  const move = {
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    promotion: uci.length > 4 ? uci.slice(4) : undefined,
  };
  return chess.move(move);
}

function renderBoard(lastMove) {
  if (!refs.board || !state.replay) return;
  refs.board.setAttribute("orientation", state.replay.player_color || "white");
  refs.board.setAttribute("position", state.chess.fen());
  highlightMove(lastMove?.uci);
  if (refs.progress) {
    refs.progress.textContent = `Move ${state.currentPly}/${state.replay.moves.length}`;
  }
  if (refs.meta) {
    const result = state.replay.winner
      ? `${state.replay.winner === "draw" ? "Draw" : state.replay.winner === "player" ? "You" : "Engine"} (${state.replay.result || ""})`
      : "In progress";
    refs.meta.textContent = `White: ${state.replay.player_color === "white" ? "You" : "Chessica"} · Black: ${
      state.replay.player_color === "black" ? "You" : "Chessica"
    } · ${result}`;
  }
}

function renderMoveList() {
  if (!refs.moves || !state.replay) return;
  refs.moves.innerHTML = "";
  if (!state.replay.moves.length) {
    refs.moves.textContent = "No moves captured for this session.";
    return;
  }
  state.replay.moves.forEach((move, idx) => {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = `replay-move ${idx + 1 === state.currentPly ? "active" : ""}`;
    pill.dataset.index = String(idx + 1);
    pill.textContent = `${move.ply}. ${move.san}`;
    refs.moves.appendChild(pill);
  });
}

function goToPly(targetPly) {
  if (!state.replay) return;
  const bounded = Math.max(0, Math.min(targetPly, state.replay.moves.length));
  state.chess = new Chess(state.replay.initial_fen || undefined);
  let lastMove = null;
  for (let i = 0; i < bounded; i += 1) {
    const move = state.replay.moves[i];
    const made = applyUci(state.chess, move.uci);
    if (!made) break;
    lastMove = move;
  }
  state.currentPly = bounded;
  renderBoard(lastMove);
  renderMoveList();
}

async function loadReplay(sessionId) {
  setStatus("Loading replay...");
  try {
    const res = await fetch(`${API_BASE}/sessions/${sessionId}/replay`);
    if (!res.ok) {
      throw new Error(`Replay not found (${res.status})`);
    }
    const data = await res.json();
    state.sessionId = sessionId;
    state.replay = data;
    state.chess = new Chess(data.initial_fen || undefined);
    state.currentPly = 0;
    goToPly(0);
    setStatus(`Loaded session ${sessionId}`);
    if (refs.copyBtn) refs.copyBtn.disabled = false;
    if (refs.downloadBtn) refs.downloadBtn.disabled = false;
  } catch (error) {
    log(error.message);
    setStatus("Unable to load that session.");
  }
}

async function copyLink() {
  const link = shareUrl();
  if (!link) return;
  try {
    await navigator.clipboard.writeText(link);
    setStatus("Link copied.");
  } catch {
    window.prompt("Copy this link:", link);
  }
}

async function downloadPgn() {
  if (!state.sessionId) return;
  try {
    const res = await fetch(`${API_BASE}/sessions/${state.sessionId}/pgn`);
    if (!res.ok) throw new Error(`Download failed (${res.status})`);
    const text = await res.text();
    const blob = new Blob([text], { type: "application/x-chess-pgn" });
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = `${state.sessionId}.pgn`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } catch (error) {
    log(error.message);
    setStatus("Could not download PGN right now.");
  }
}

function hookControls() {
  if (refs.form) {
    refs.form.addEventListener("submit", (event) => {
      event.preventDefault();
      const id = refs.sessionInput?.value?.trim();
      if (!id) return;
      loadReplay(id);
    });
  }
  document.querySelectorAll("[data-step]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!state.replay) return;
      const action = btn.getAttribute("data-step");
      if (action === "start") goToPly(0);
      if (action === "prev") goToPly(Math.max(0, state.currentPly - 1));
      if (action === "next") goToPly(state.currentPly + 1);
      if (action === "end") goToPly(state.replay.moves.length);
    });
  });
  if (refs.moves) {
    refs.moves.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const index = Number(target.dataset.index);
      if (Number.isFinite(index)) {
        goToPly(index);
      }
    });
  }
  if (refs.copyBtn) {
    refs.copyBtn.addEventListener("click", copyLink);
  }
  if (refs.downloadBtn) {
    refs.downloadBtn.addEventListener("click", downloadPgn);
  }
}

function initFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("session");
  if (fromQuery && refs.sessionInput) {
    refs.sessionInput.value = fromQuery;
    loadReplay(fromQuery);
  }
}

hookControls();
initFromQuery();
