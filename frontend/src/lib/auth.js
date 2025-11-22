export function getAuthToken() {
  return localStorage.getItem("chessica_token");
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem("chessica_token", token);
  } else {
    localStorage.removeItem("chessica_token");
  }
}

export function clearAuthToken() {
  localStorage.removeItem("chessica_token");
}
