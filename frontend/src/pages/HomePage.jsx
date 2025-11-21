import { Link } from "react-router-dom";
import LogoMark from "../components/LogoMark";

function HomePage() {
  return (
    <div className="landing">
      <header className="hero landing-hero">
        <div className="hero-title">
          <div className="badge">
            <LogoMark />
          </div>
          <div>
            <h1>Welcome to Chessica</h1>
            <p>Pick your arena: battle the exploit-aware engine or meet humans in online play.</p>
          </div>
        </div>
        <span className="pill">Alpha</span>
      </header>

      <section className="cta-grid">
        <article className="cta-card">
          <h2>Play vs Computer</h2>
          <p>Use difficulty presets, live narration, and coach summaries without CDN dependencies.</p>
          <Link className="cta-button" to="/computer">
            Launch Control Room
          </Link>
        </article>
        <article className="cta-card">
          <h2>Play Online</h2>
          <p>Queue for multiplayer matchmaking with board streaming and clocked time controls.</p>
          <Link className="cta-button secondary" to="/multiplayer">
            Open Online Mode
          </Link>
        </article>
        <article className="cta-card">
          <h2>Replay Sessions</h2>
          <p>Load any session id, scrub through the moves, and download PGN for study.</p>
          <Link className="cta-button secondary" to="/replay">
            Replay Games
          </Link>
        </article>
      </section>
    </div>
  );
}

export default HomePage;
