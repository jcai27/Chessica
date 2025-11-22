const PROD_API_BASE = import.meta.env.VITE_API_BASE || "https://chessica-1nh3.onrender.com";
const PROD_WS_BASE = import.meta.env.VITE_WS_BASE || "wss://chessica-1nh3.onrender.com";
const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_BASE = `${isLocal ? "http://localhost:8000" : PROD_API_BASE}/api/v1`;
export const WS_BASE = `${isLocal ? "ws://localhost:8000" : PROD_WS_BASE}/api/v1`;
export const DEFAULT_TIME_CONTROL = { initial_ms: 300000, increment_ms: 0 }; // 5+0 blitz
