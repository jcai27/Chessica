import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE } from "../lib/config";
import { setAuthToken, clearAuthToken } from "../lib/auth";

function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    const endpoint = mode === "signup" ? "/auth/sign-up" : "/auth/sign-in";
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, remember: true }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Auth failed (${res.status})`);
      }
      const data = await res.json();
      if (data.token) {
        setAuthToken(data.token);
        if (onAuth) onAuth(data.user);
        navigate("/computer");
      }
    } catch (err) {
      setError(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    if (onAuth) onAuth(null);
    setEmail("");
    setPassword("");
    setError("");
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-badge">
              <span>♟︎</span>
            </div>
            <h1>Chessica</h1>
            <p className="muted">Master chess through AI-powered exploit learning</p>
          </div>

          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${mode === "login" ? "active" : ""}`}
              onClick={() => setMode("login")}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`auth-tab ${mode === "signup" ? "active" : ""}`}
              onClick={() => setMode("signup")}
            >
              Sign Up
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                required
                disabled={loading}
              />
            </div>

            <div className="auth-field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={loading}
              />
            </div>

            {error && (
              <div className="auth-error">
                <span>⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? "Please wait..." : mode === "signup" ? "Create Account" : "Sign In"}
            </button>
          </form>

          <div className="auth-footer">
            <p className="muted">
              {mode === "login" ? "Don't have an account? " : "Already have an account? "}
              <button
                type="button"
                className="auth-link"
                onClick={() => setMode(mode === "login" ? "signup" : "login")}
              >
                {mode === "login" ? "Sign up" : "Sign in"}
              </button>
            </p>
          </div>

          <div className="auth-divider">
            <span>or</span>
          </div>

          <button type="button" className="auth-secondary" onClick={handleLogout}>
            Clear Session
          </button>
        </div>

        <div className="auth-features">
          <div className="feature-item">
            <div className="feature-icon">📊</div>
            <div>
              <strong>Track Progress</strong>
              <p className="muted">Sync ratings across all devices</p>
            </div>
          </div>
          <div className="feature-item">
            <div className="feature-icon">🎯</div>
            <div>
              <strong>AI Coaching</strong>
              <p className="muted">Real-time position analysis</p>
            </div>
          </div>
          <div className="feature-item">
            <div className="feature-icon">🧠</div>
            <div>
              <strong>Exploit Learning</strong>
              <p className="muted">Master opponent modeling</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AuthPage;
