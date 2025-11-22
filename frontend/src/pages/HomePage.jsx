import { Link } from "react-router-dom";
import LogoMark from "../components/LogoMark";

const modes = [
  {
    title: "Engine Lab",
    description: "Stockfish with exploit-aware patches, guided narration, and coach-style recaps.",
    meta: "Local, no CDN",
    cta: "Play vs Computer",
    to: "/computer",
    tone: "primary",
  },
  {
    title: "Online Queue",
    description: "Clocked multiplayer with streamed boards and fair pairing expectations.",
    meta: "Live opponents",
    cta: "Go Online",
    to: "/multiplayer",
  },
  {
    title: "Replay Room",
    description: "Load any session id, scrub the move list, and export PGN for study.",
    meta: "Study & share",
    cta: "Browse Replays",
    to: "/replay",
  },
];

const highlights = [
  "Local-first setup with no third-party CDN dependencies.",
  "Narration, PGN export, and move scrubber built in.",
  "Engine controls tuned for quick testing or deeper drills.",
];

function HomePage() {
  return (
    <div className="landing landing-shell">
      <header className="landing-hero">
        <div className="hero-copy">
          <div className="pill pill-soft">Alpha build</div>
          <h1>Command Chessica&apos;s board</h1>
          <p>
            Launch straight into an engine lab, queue for humans, or drop into a replay room. Buttons stay anchored so
            you can hop modes without losing your place.
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
            <span className="point-chip">Narration + PGN export</span>
            <span className="point-chip">Local-first, zero CDN</span>
          </div>
        </div>
        <div className="hero-panel card">
          <div className="hero-panel__heading">
            <div className="badge small">
              <LogoMark />
            </div>
            <div>
              <p className="eyebrow">Launch bay</p>
              <strong>Pick a mode to boot instantly.</strong>
              <span className="muted">Keeps to the viewport so you can swap without scrolling.</span>
            </div>
          </div>
          <div className="hero-panel__actions">
            {modes.map((mode) => (
              <Link key={mode.to} className="cta-chip primary wide" to={mode.to}>
                {mode.cta}
              </Link>
            ))}
          </div>
          <div className="hero-panel__meta">
            <div className="meta-chip">
              <span className="dot success" />
              Local compute, no cloud costs.
            </div>
            <div className="meta-chip">
              <span className="dot accent" />
              Live controls stay sticky.
            </div>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="mode-section card">
          <div className="section-title">
            <div>
              <p className="eyebrow">Modes</p>
              <h2>Pick how you want to play</h2>
            </div>
            <span className="muted">Buttons are grouped, not full-bleed.</span>
          </div>
          <div className="mode-grid">
            {modes.map((mode) => (
              <article key={mode.title} className={`mode-card ${mode.tone ?? ""}`}>
                <div className="mode-card__top">
                  <h3>{mode.title}</h3>
                  <span className="mode-meta">{mode.meta}</span>
                </div>
                <p>{mode.description}</p>
                <Link className="cta-chip ghost" to={mode.to}>
                  {mode.cta}
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="info-grid">
          <article className="info-card card">
            <div className="section-title">
              <div>
                <p className="eyebrow">What&apos;s inside</p>
                <h3>Comfortable controls for quick sessions</h3>
              </div>
              <span className="pill pill-soft">Fast setup</span>
            </div>
            <ul className="note-list">
              {highlights.map((item) => (
                <li key={item}>
                  <span className="dot accent" />
                  {item}
                </li>
              ))}
            </ul>
          </article>

          <article className="info-card card">
            <div className="section-title">
              <div>
                <p className="eyebrow">Replay-ready</p>
                <h3>Keep track of every run</h3>
              </div>
              <span className="pill pill-soft">Study mode</span>
            </div>
            <p className="muted">
              Replays sit one tap away from the hero buttons so you can load a session id, scrub moves, and export PGN
              without hunting through menus.
            </p>
            <div className="callout">
              <div>
                <strong>Jump straight in</strong>
                <p className="muted">Open the replay room to continue where you left off.</p>
              </div>
              <Link className="cta-chip primary" to="/replay">
                Open Replay Room
              </Link>
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}

export default HomePage;
