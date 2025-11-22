import { useEffect, useMemo, useState } from "react";
import LogoMark from "../components/LogoMark";
import { api } from "../lib/api";
import { clearAuth, getAuthUser, saveAuth } from "../lib/auth";

function AuthPage() {
  const [featureEnabled, setFeatureEnabled] = useState(true);
  const [featureLoading, setFeatureLoading] = useState(true);
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");
  const [signUpRemember, setSignUpRemember] = useState(true);
  const [signInPending, setSignInPending] = useState(false);
  const [signUpPending, setSignUpPending] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [currentUser, setCurrentUser] = useState(getAuthUser());
  const [checkingSession, setCheckingSession] = useState(false);

  const pillTone = useMemo(() => {
    if (featureLoading) return "";
    return featureEnabled ? "success" : "warn";
  }, [featureEnabled, featureLoading]);

  useEffect(() => {
    api
      .authFeature()
      .then((res) => {
        if (typeof res?.enabled === "boolean") {
          setFeatureEnabled(res.enabled);
        }
      })
      .catch(() => setFeatureEnabled(false))
      .finally(() => setFeatureLoading(false));
  }, []);

  const disabled = featureLoading || !featureEnabled;

  const showFeedback = (message, tone = "info") => {
    setFeedback({ message, tone });
  };

  const refreshSession = async () => {
    setCheckingSession(true);
    try {
      const data = await api.me();
      saveAuth({ token: getAuthUser()?.token, user: data });
      setCurrentUser(data);
      showFeedback("Session refreshed.", "good");
    } catch (err) {
      showFeedback(err.message || "Unable to refresh session.", "bad");
    } finally {
      setCheckingSession(false);
    }
  };

  const handleSignIn = async (event) => {
    event.preventDefault();
    if (!signInEmail || !signInPassword) {
      showFeedback("Email and password required.", "bad");
      return;
    }
    setSignInPending(true);
    try {
      const data = await api.signIn({ email: signInEmail.trim(), password: signInPassword });
      saveAuth(data);
      setCurrentUser(data.user);
      showFeedback(`Signed in as ${data?.user?.username || signInEmail}.`, "good");
    } catch (err) {
      showFeedback(err.message || "Sign-in failed.", "bad");
    } finally {
      setSignInPending(false);
    }
  };

  const handleSignUp = async (event) => {
    event.preventDefault();
    if (!signUpEmail || !signUpPassword) {
      showFeedback("Email and password required.", "bad");
      return;
    }
    setSignUpPending(true);
    try {
      const data = await api.signUp({
        email: signUpEmail.trim(),
        password: signUpPassword,
        remember: signUpRemember,
      });
      saveAuth(data);
      setCurrentUser(data.user);
      showFeedback(`Welcome, ${data?.user?.username || signUpEmail}!`, "good");
    } catch (err) {
      showFeedback(err.message || "Sign-up failed.", "bad");
    } finally {
      setSignUpPending(false);
    }
  };

  const handleSignOut = () => {
    clearAuth();
    setCurrentUser(null);
    showFeedback("Signed out.", "info");
  };

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-title">
          <div className="badge">
            <LogoMark />
          </div>
          <div>
            <h1>Accounts & Profiles</h1>
            <p className="muted">
              Email sign-in, code-based login, and password signup. Ties into the API auth stubs so you can start
              testing flows early.
            </p>
          </div>
        </div>
        <span className={`pill ${pillTone}`}>{featureLoading ? "Checking..." : featureEnabled ? "Enabled" : "Disabled"}</span>
      </header>

      <section className="card auth-card">
        <div className="auth-banner">
          <div>
            <strong>{featureEnabled ? "Auth preview is live" : "Auth disabled"}</strong>
            <p>
              {featureEnabled
                ? "Use email + code or email + password. Tokens are stored locally."
                : "Backend feature flag is off. Enable it to test auth."}
            </p>
          </div>
          {currentUser ? <span className="pill success">Signed in</span> : <span className="pill">Preview</span>}
        </div>

        {feedback?.message ? (
          <div
            className={`status-banner ${
              feedback.tone === "bad" ? "is-bad" : feedback.tone === "good" ? "is-good" : ""
            }`}
          >
            {feedback.message}
          </div>
        ) : null}

        <div className="auth-layout">
          <form className="auth-form" onSubmit={handleSignIn}>
            <h2>Email Sign In</h2>
            <p className="muted">Use your email and password to log in.</p>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={signInEmail}
                onChange={(e) => setSignInEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={disabled}
                required
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={signInPassword}
                onChange={(e) => setSignInPassword(e.target.value)}
                placeholder="••••••••"
                disabled={disabled}
                required
              />
            </label>
            <div className="inline-actions">
              <button type="submit" className="secondary" disabled={disabled || signInPending}>
                {signInPending ? "Signing in..." : "Sign in"}
              </button>
            </div>
          </form>

          <form className="auth-form" onSubmit={handleSignUp}>
            <h2>Create Account</h2>
            <p className="muted">Password-based signup stub that issues a dev token.</p>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={signUpEmail}
                onChange={(e) => setSignUpEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={disabled}
                required
              />
            </label>
            <label>
              <span>Password</span>
              <input
                type="password"
                value={signUpPassword}
                onChange={(e) => setSignUpPassword(e.target.value)}
                placeholder="••••••••"
                disabled={disabled}
                required
              />
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={signUpRemember}
                onChange={(e) => setSignUpRemember(e.target.checked)}
                disabled={disabled}
              />
              <span className="toggle-shape" />
              <span>Keep me signed in</span>
            </label>
            <button type="submit" disabled={disabled || signUpPending}>
              {signUpPending ? "Creating..." : "Create account"}
            </button>
            <div className="pending-hint">Stubbed for now; backend will swap in real storage later.</div>
          </form>
        </div>
      </section>

      <section className="card share-card">
        <div className="share-header">
          <h3>Current session</h3>
          <span>{currentUser ? "Token stored locally" : "Not signed in"}</span>
        </div>
        {currentUser ? (
          <>
            <div className="share-actions">
              <div className="share-link" aria-label="Current user">
                <strong>{currentUser.username}</strong>
                <div className="muted">{currentUser.user_id}</div>
              </div>
              <div className="note-list">
                <div className="meta-chip">
                  <span className="dot accent" />
                  Default exploit mode: {currentUser.exploit_default}
                </div>
                <div className="meta-chip">
                  <span className="dot success" />
                  Rating hint: {currentUser.rating_hint ?? "n/a"}
                </div>
              </div>
            </div>
            <div className="inline-actions">
              <button className="secondary" type="button" onClick={handleSignOut}>
                Sign out
              </button>
              <button type="button" onClick={refreshSession} disabled={checkingSession}>
                {checkingSession ? "Checking..." : "Refresh /me"}
              </button>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <span className="emoji">👤</span>
            <span>Sign in or sign up to store a token for API calls.</span>
          </div>
        )}
      </section>
    </div>
  );
}

export default AuthPage;
