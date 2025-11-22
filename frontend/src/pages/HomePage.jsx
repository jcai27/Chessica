import { Link } from "react-router-dom";
import LogoMark from "../components/LogoMark";

const quickLinks = [
  {
    title: "Play vs Computer",
    description: "Engine lab with coach, plans, and structured analysis.",
    to: "/computer",
    tone: "primary",
  },
  {
    title: "Online Match",
    description: "Queue, pair, and play humans with clocks that stay in sync.",
    to: "/multiplayer",
  },
  {
    title: "Replay Room",
    description: "Load a session id, scroll moves, export PGN.",
    to: "/replay",
  },
];

function HomePage() {
  return (
    <div className="landing landing-shell">
      <header className="landing-hero">
        <div className="hero-copy">
          <div className="pill pill-soft">Chessica</div>
          <h1>Three ways to play, no clutter</h1>
          <p className="muted">
            Drop into the engine lab, queue online, or review a session. Everything fits on screen and stays lean.
          </p>
          <div className="hero-actions">
            <Link className="cta-chip primary" to="/computer">
              Start vs Computer
            </Link>
            <Link className="cta-chip ghost" to="/multiplayer">
              Find Online Match
            </Link>
            <Link className="cta-chip ghost" to="/replay">
              Open Replays
            </Link>
          </div>
          <div className="hero-points">
            <span className="point-chip">Exploit-aware Stockfish</span>
            <span className="point-chip">Coach + analysis built in</span>
          </div>
        </div>
        <div className="hero-panel card">
          <div className="hero-panel__heading">
            <div className="badge small">
              <LogoMark />
            </div>
            <div>
              <p className="eyebrow">Quick launch</p>
              <strong>Pick a lane and go.</strong>
              <span className="muted">No scrolling, just play.</span>
            </div>
          </div>
          <div className="hero-panel__actions">
            {quickLinks.map((mode) => (
              <Link key={mode.to} className="cta-chip primary wide" to={mode.to}>
                {mode.title}
              </Link>
            ))}
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="mode-section card">
          <div className="section-title">
            <div>
              <p className="eyebrow">Shortcuts</p>
              <h2>Choose your next action</h2>
            </div>
            <span className="muted">Kept compact on purpose.</span>
          </div>
          <div className="mode-grid compact">
            {quickLinks.map((mode) => (
              <article key={mode.title} className={`mode-card ${mode.tone ?? ""}`}>
                <div className="mode-card__top">
                  <h3>{mode.title}</h3>
                </div>
                <p className="muted">{mode.description}</p>
                <Link className="cta-chip ghost" to={mode.to}>
                  Enter
                </Link>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default HomePage;
