const STORAGE_KEY = "chessica_auth";

function safeParse(value) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    return {};
  }
}

export function loadAuth() {
  if (typeof localStorage === "undefined") return null;
  const data = safeParse(localStorage.getItem(STORAGE_KEY));
  if (!data?.token || !data?.user) return null;
  return data;
}

export function saveAuth(payload) {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      token: payload?.token,
      user: payload?.user,
    }),
  );
}

export function clearAuth() {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

export function getAuthToken() {
  return loadAuth()?.token || null;
}

export function getAuthUser() {
  return loadAuth()?.user || null;
}
