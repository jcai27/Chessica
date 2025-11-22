import { getAuthToken } from "./auth";
import { API_BASE } from "./config";

async function request(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed with ${res.status}`);
  }
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res.text();
}

export const api = {
  authFeature() {
    return request("/auth/feature");
  },
  sendLoginCode(email) {
    return request("/auth/send-code", { method: "POST", body: JSON.stringify({ email }) });
  },
  signIn(payload) {
    return request("/auth/sign-in", { method: "POST", body: JSON.stringify(payload) });
  },
  signUp(payload) {
    return request("/auth/sign-up", { method: "POST", body: JSON.stringify(payload) });
  },
  me() {
    return request("/me");
  },
  createSession(payload) {
    return request("/sessions", { method: "POST", body: JSON.stringify(payload) });
  },
  sessionDetail(sessionId) {
    return request(`/sessions/${sessionId}`);
  },
  move(sessionId, payload) {
    return request(`/sessions/${sessionId}/moves`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  analysis(sessionId) {
    return request(`/sessions/${sessionId}/analysis`);
  },
  coach(sessionId) {
    return request(`/sessions/${sessionId}/coach`, { method: "POST" });
  },
  pgn(sessionId) {
    return request(`/sessions/${sessionId}/pgn`);
  },
  replay(sessionId) {
    return request(`/sessions/${sessionId}/replay`);
  },
  queueJoin(payload) {
    return request(`/multiplayer/queue`, { method: "POST", body: JSON.stringify(payload) });
  },
  queueStatus(playerId) {
    return request(`/multiplayer/queue/${playerId}`);
  },
  queueLeave(playerId) {
    return request(`/multiplayer/queue/${playerId}`, { method: "DELETE" });
  },
  createMultiplayer(payload) {
    return request(`/multiplayer/sessions`, { method: "POST", body: JSON.stringify(payload) });
  },
  multiplayerMove(sessionId, payload) {
    return request(`/multiplayer/sessions/${sessionId}/moves`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  multiplayerAction(sessionId, action) {
    return request(`/multiplayer/sessions/${sessionId}/${action}`, { method: "POST" });
  },
};
