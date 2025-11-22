import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE } from "../lib/config";
import { setAuthToken, clearAuthToken } from "../lib/auth";

function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
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
    <div className="app">
      <div className="page-grid">
        <section className="card hero hero-card">
          <div className="hero-title">
            <div className="badge">
              <span role="img" aria-label="lock">
                🔐
              </span>
            </div>
            <div>
              <h1>{mode === "signup" ? "Create account" : "Sign in"}</h1>
              <p>Sign in to sync ratings and preferences across devices.</p>
            </div>
          </div>
        </section>

        <section className="card tab-card">
          <div className="tab-bar">
            <button type="button" className={`tab-button ${mode === "login" ? "active" : ""}`} onClick={() => setMode("login")}>
              Login
            </button>
            <button type="button" className={`tab-button ${mode === "signup" ? "active" : ""}`} onClick={() => setMode("signup")}>
              Sign Up
            </button>
            <button type="button" className="tab-button" onClick={handleLogout}>
              Logout
            </button>
          </div>
          <div className="tab-panel">
            <form className="controls-form" onSubmit={handleSubmit}>
              <label className="select-field">
                <span>Email</span>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label className="select-field">
                <span>Password</span>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </label>
              {error && <div className="difficulty-indicator">{error}</div>}
              <button type="submit">{mode === "signup" ? "Create account" : "Login"}</button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}

export default AuthPage;
