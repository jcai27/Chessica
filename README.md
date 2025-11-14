# Chessica: Exploit-Aware Chess Engine

## 1. Introduction & Motivation
Modern AlphaZero-style engines assume optimal adversaries and optimize for objective accuracy through self-play. Humans, however, make systematic, non-optimal mistakes that a purely objective engine neither anticipates nor provokes. Chessica aims to flip the perspective: build an engine that *plays the player* by steering positions toward likely human errors without throwing away the game. The end product is a public web app and API where users can play the engine, receive real-time explanations, and review post-game analyses tailored to their tendencies.

## 2. Problem Statement & Objectives
**Problem.** Maximize expected win rate against human opponents by exploiting personalized error patterns while remaining robust when the model is uncertain.

**Objectives.**
1. Integrate explicit opponent modeling into a policy/value + MCTS engine.
2. Quantify exploitative advantage over a non-personalized baseline.
3. Deliver a low-latency web experience with human-readable move explanations.

## 3. Background & Related Work
- AlphaZero/Leela: combined policy/value networks with Monte Carlo Tree Search via self-play.
- Opponent modeling: established in poker, RTS, and other imperfect-information domains.
- Existing chess personalization: mainly handicaps or rating-scaled bots; Chessica differs by learning actionable, motif-level exploit strategies.

## 4. System Overview
**Frontend:** Chessboard UI, move list, explanation panel, controls (strength slider, exploit toggle).  
**Backend API:** REST/WebSocket endpoints for move requests, annotations, game/session management.  
**Engine Service:** Batched GPU inference for policy/value network \(f_\theta\), opponent model \(g_\phi\), MCTS with exploit-aware selection, transposition tables.  
**Data Layer:** User accounts, games, opponent profiles, telemetry/logging (Postgres + Redis/in-memory cache).  

### 4.1 Architecture Views
#### High-Level Component Diagram
```mermaid
graph TD
    A[Web Client<br/>React/Next] -->|HTTPS/WebSocket| B(API Gateway<br/>REST & WS)
    B --> C[Game Service<br/>Go/Node/Python]
    C -->|state mutations| D[(Postgres<br/>users/games)]
    C -->|active sessions| E[(Redis / In-Memory Cache)]
    C -->|enqueue jobs| F[Task Queue<br/>(e.g., NATS, RabbitMQ)]
    F --> G[Engine Worker Pool]
    G --> H[Engine Core<br/>MCTS + Transposition]
    H --> I[Policy/Value Runner<br/>GPU inference]
    H --> J[Opponent Model Runner]
    J --> K[(Opponent Profiles<br/>feature store)]
    C --> L[Explainability Service]
    L --> H
    G --> M[Logging & Metrics<br/>(OpenTelemetry + OLAP)]
```

**Responsibilities.**
- **Web client** handles move entry, analysis display, and explanation UI.
- **API Gateway** terminates TLS, handles auth/rate limiting, routes to core services.
- **Game Service** orchestrates sessions, talks to storage/cache, and coordinates engine jobs.
- **Engine Workers** execute MCTS with calls to neural services; scale horizontally with GPU-backed runners.
- **Explainability Service** formats natural-language rationales from engine statistics and opponent insights.
- **Data Stores** persist long-lived entities (Postgres), fast-changing game trees (Redis), and offline analytics (OLAP).

#### Move Evaluation Sequence
```mermaid
sequenceDiagram
    participant P as Player
    participant W as Web Client
    participant A as API Gateway
    participant G as Game Service
    participant R as Redis Cache
    participant Q as Task Queue
    participant E as Engine Worker
    participant N as NN Runners (fθ, gφ)
    participant X as Explainability Service

    P->>W: Submit move / request engine reply
    W->>A: HTTPS POST /sessions/{id}/moves
    A->>G: Forward authenticated payload
    G->>R: Update session state, fetch context
    G->>Q: Enqueue engine job (board, timers, opponent state)
    Q-->>E: Deliver job
    E->>N: Batched inference for policy/value + opponent model
    N-->>E: Priors, values, exploit estimates
    E->>E: Run exploit-aware MCTS, pick move
    E->>X: Request explanation template inputs
    X-->>E: Natural-language rationale snippets
    E-->>G: Move result + explanation + updated opponent belief
    G->>R: Cache updated game tree/opponent state
    G->>A: Response payload (move, eval, explanation)
    A-->>W: HTTP 200 + JSON
    W-->>P: Render engine move and explanation
```

#### Deployment Considerations
- Separate stateless API tier from stateful engine workers to allow independent autoscaling.
- Keep Redis co-located with engine workers to minimize tree/node serialization latency.
- Expose inference runners via gRPC/Batched RPC to make GPU utilization efficient across matches.

## 5. Modeling Components
### 5.1 Policy/Value Network
- **Inputs:** Board state plus optional game context (move count, repetition flags, material phase).
- **Outputs:** Move priors (policy head) and objective evaluation vs strong play (value head).
- **Architecture:** ResNet-style conv net; reuse or fine-tune existing AlphaZero/Leela weights if practical.

### 5.2 Opponent Model
- **Inputs:** Rating (if available), time control, per-move time usage, recent move history, motif tags (tactics/endgames/imbalances).
- **Outputs:** Error probabilities per motif/position cluster, latent style params (tactical vs positional, risk profile, time-pressure fragility).
- **Belief Updating:** Online Bayesian or recurrent update per move to refine opponent profile mid-game.

### 5.3 Exploitative Search (MCTS Variant)
- Selection formula: standard \(Q + \text{PUCT}\) term plus an exploit bonus proportional to predicted opponent error rate following each candidate move.
- Uncertainty-aware weighting: shrink exploit term when opponent model confidence is low.
- Guardrails: cap allowable drop in objective eval to avoid intentional blunders; ensure fallback to best-play policy when uncertain.

## 6. Data & Training
### 6.1 Self-Play Data
- Generate self-play or leverage open AlphaZero/Leela datasets to train the policy/value net and maintain strong baseline play.

### 6.2 Human Game Data
- Collect a large corpus of rated human games with timestamps; annotate using a strong reference engine to label blunders/inaccuracies and motif classes.

### 6.3 Training Procedures
- Policy/value: supervised pretraining on strong games + RL fine-tuning via self-play.
- Opponent model: train to predict human error probabilities from (state, features); augment with simulated populations exhibiting sampled style parameters to improve coverage.

## 7. Implementation Plan
### 7.1 Backend Engine Service
- Implement MCTS with transposition tables and batched GPU inference hooks.
- Integrate opponent model inference and per-game belief states.
- Provide safe fallbacks when exploit scoring conflicts with objective evaluation limits.
- Current prototype ships with a python-chess-powered alpha-beta search (depth configurable per session) that adds mobility, king safety, and quiescence heuristics in lieu of the eventual neural policy/value.

### 7.2 Web & API Layer
- REST/WebSocket API for move requests and explanation retrieval.
- Frontend with chessboard, move history, explanation panel (“why this move” + “what the engine thinks about you”), settings (strength slider, exploit toggle).

### 7.3 Infrastructure
- Single GPU instance for inference (MVP), Postgres for persistence, Redis/in-memory cache for active games and trees, structured logging and monitoring.

## 8. Evaluation
### 8.1 Quantitative vs Humans
- A/B test exploit mode on/off; track win/draw/loss by rating band, induced blunder rates, opponent time usage shifts.

### 8.2 Safety & Strength
- Play vs standard engines to measure Elo delta and ensure exploit mode does not catastrophically weaken baseline strength.

### 8.3 Ablations
- Remove opponent-model features (motifs, rating, timing, etc.) and vary exploit weight/uncertainty thresholds to isolate contributions.

## 9. User-Facing Explainability
- Per-move text like: “You’ve struggled with tactical forks; this continuation increases fork motifs in 3–5 moves at minimal eval cost.”
- Post-game summary with style radar, explanation of deliberate steering, educational comparisons between objective-best and exploitative moves.

## 10. Ethics, Privacy, UX
- Inform users the engine adapts to exploit weaknesses; offer “exploit me” vs “objective play” toggle.
- Ensure data anonymization, deletion requests, and clear policy on fairness (e.g., not for rated competition without disclosure).

## 11. Timeline (Example)
- **Month 1:** Integrate baseline policy/value + MCTS, rudimentary opponent model (rating/time), CLI play.
- **Month 2:** Train opponent model v1 on human data, integrate exploitative search, internal evaluations.
- **Month 3:** Launch public web app/API, run A/B experiments, build dashboards, draft research write-up.

## 12. Expected Contributions
1. Reference architecture for exploit-aware chess search.
2. Empirical evidence on benefits of opponent modeling in chess.
3. Public demo showcasing human-optimal play concepts, with potential open-source release.

## 13. API Contracts
### 13.1 Authentication & Versioning
- All REST endpoints are rooted at `/api/v1`.
- Auth via short-lived JWT obtained through existing identity provider (future work).
- WebSocket connections must include `Authorization: Bearer <token>` header during upgrade.

### 13.2 Session Lifecycle
#### `POST /api/v1/sessions`
| Field | Type | Description |
| --- | --- | --- |
| `variant` | string | `"standard"` (future: chess960). |
| `time_control` | object | `{initial_ms, increment_ms}` |
| `color` | string | `"white"`, `"black"`, or `"auto"`. |
| `exploit_mode` | string | `"auto"`, `"on"`, `"off"`. |
| `difficulty` | string | Optional preset (`beginner`, …, `grandmaster`). |
| `engine_rating` | integer | Optional Elo target (600–2800); maps to the nearest preset. |
| `engine_depth` | integer | Optional manual search depth override (1–5). Defaults to server setting. |

**Response 201.**
```json
{
  "session_id": "sess_123",
  "engine_color": "black",
  "player_color": "white",
  "exploit_mode": "auto",
  "difficulty": "advanced",
  "engine_rating": 1600,
  "engine_depth": 3,
  "status": "active",
  "created_at": "2024-03-18T12:00:00Z"
}
```

#### `POST /api/v1/sessions/{sessionId}/moves`
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `uci` | string | yes | Player move in UCI (or `"null"` if asking engine to move first). |
| `client_ts` | string | yes | ISO timestamp for latency measurement. |
| `clock` | object | yes | `{player_ms, engine_ms}` remaining clocks. |
| `telemetry` | object | no | Optional client hints (e.g., `"hover_square"`, `"premove": true`). |

**Response 200.**
```json
{
  "engine_move": "e7e5",
  "engine_eval_cp": 28,
  "exploit_confidence": 0.73,
  "opponent_profile": {
    "style": {"tactical": 0.61, "risk": 0.38},
    "motif_risk": {"forks": 0.8, "back_rank": 0.42}
  },
  "explanation": {
    "summary": "You hesitated in open tactical fights; this line invites fork motifs.",
    "objective_cost_cp": 12,
    "alt_best_move": "g8f6",
    "alt_eval_cp": 40
  },
  "game_state": {
    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 1 2",
    "move_number": 2,
    "turn": "white"
  },
  "result": null,
  "winner": null,
  "message": null
}
```
If a move ends the game (checkmate, stalemate, or resignation), the response returns `engine_move: null` (when the engine has no reply), alongside `result`, `winner`, and a friendly `message` so clients can conclude gracefully.

### Difficulty Scale
| Level | Approx. Rating | Search Depth |
| --- | --- | --- |
| Beginner | ~800 | 1 ply + quiescence |
| Intermediate | ~1200 | 2 ply |
| Advanced | ~1600 | 3 ply (default) |
| Expert | ~2000 | 4 ply |
| Grandmaster | ~2400 | 5 ply |

Use `difficulty` on session creation (or the frontend dropdown) to select a preset. For finer control, pass `engine_rating` or `engine_depth`; the server will map those to the closest preset or mark them as `custom`.

#### `GET /api/v1/sessions/{sessionId}`
- Returns current board, clocks, opponent profile snapshot, and moves list for resuming games.

#### `POST /api/v1/sessions/{sessionId}/resign`
- Marks session complete; response includes final PGN and summary stats.

### 13.3 Explanations & Analysis
#### `GET /api/v1/sessions/{sessionId}/analysis`
Query params: `depth`, `perspective` (`"objective"` or `"exploit"`).

**Response.**
```json
{
  "session_id": "sess_123",
  "moves": [
    {
      "ply": 10,
      "player_move": "d4",
      "engine_reply": "c5",
      "objective_eval_cp": -34,
      "exploit_gain_cp": 22,
      "motifs": ["isolated pawn", "fork threat"],
      "explanation": "Steers to IQP structures where you rush pawn breaks."
    }
  ],
  "summary": {
    "induced_blunders": 3,
    "eval_tradeoff_cp": 41,
    "themes": ["fork pressure", "time squeeze"]
  }
}
```

### 13.4 Real-Time Streaming
#### `wss://.../api/v1/sessions/{sessionId}/stream`
- Bi-directional updates for moves, clocks, and incremental explanations.
- Messages are JSON envelopes:
```json
{
  "type": "engine_move",
  "payload": {
    "uci": "c7c5",
    "search_nodes": 120345,
    "nps": 550000,
    "best_line": ["c7c5", "d2d4", "c5d4"]
  }
}
```

### 13.5 User & Profile Endpoints
#### `GET /api/v1/me`
- Returns authenticated user metadata, rating baseline, and privacy preferences.

#### `PATCH /api/v1/me/preferences`
Fields: `exploit_default`, `share_data_opt_in`, notification settings.

### 13.6 Data Models (Common)
- **Session:** `{session_id, status, variant, seed_fen, player_color, exploit_mode, clocks, created_at, updated_at}`.
- **OpponentProfile:** `{rating_hint, style_vector[5], motif_risk_map, uncertainty, recent_errors}`.
- **Explanation:** `{summary, detail, objective_cost_cp, exploit_gain_cp, supporting_variation[]}`.
- **MoveTelemetry:** `{hover_sq, premove, think_time_ms, ui_version}` for analytics and opponent modeling.

### 13.7 Analytics
#### `GET /api/v1/analytics/sessions/{sessionId}/events`
- Returns a chronological list of engine/player events plus aggregate counts.

**Response.**
```json
{
  "session_id": "sess_123",
  "events": [
    {
      "id": 42,
      "event_type": "player_move",
      "payload": {"uci": "e2e4", "clocks": {"player_ms": 298000, "engine_ms": 300000}},
      "created_at": "2024-03-18T12:01:00Z"
    },
    {
      "id": 43,
      "event_type": "engine_move",
      "payload": {"uci": "c7c5", "engine_eval_cp": 35, "...": "..."},
      "created_at": "2024-03-18T12:01:01Z"
    }
  ],
  "summary": {
    "total_events": 12,
    "counts_by_type": {"player_move": 6, "engine_move": 6},
    "last_event_at": "2024-03-18T12:05:10Z"
  }
}
```

## 14. Implementation Status & Getting Started
### 14.1 Repository Layout
```
.
├── README.md           # Project overview + architecture + API contracts
├── backend/
│   ├── app/
│   │   ├── api/        # FastAPI routers (sessions, analysis, users, stream)
│   │   ├── board.py    # python-chess wrapper for legality + FEN updates
│   │   ├── engine.py   # Mock engine hooks (to be replaced with real engine service clients)
│   │   ├── main.py     # FastAPI application factory
│   │   ├── schemas.py  # Pydantic models for requests/responses
│   │   ├── store.py    # Session repository (Postgres + Redis cache ready)
│   │   ├── cache.py    # Redis-backed cache with in-process fallback
│   │   ├── database.py # SQLAlchemy engine/session helpers
│   │   └── models.py   # SQLAlchemy models (sessions, engine events)
│   └── pyproject.toml  # Poetry configuration (FastAPI, SQLAlchemy, python-chess)
└── frontend/
    ├── index.html      # Static UI prototype
    ├── app.js          # REST + WebSocket wiring
    └── styles.css      # Styling + board rendering
```

### 14.2 Running the API Locally
1. **Install dependencies + Stockfish**
   ```bash
   cd backend
   # Install Stockfish (example for Ubuntu/WSL)
   sudo apt install stockfish
   # Optional: point the API to your binary
   export STOCKFISH_PATH=/usr/bin/stockfish
   poetry install
   ```
2. **Run the dev server**
   ```bash
   poetry run uvicorn app.main:app --reload
   ```
3. **Explore the docs** at `http://localhost:8000/docs` (FastAPI Swagger UI) to exercise the stubbed endpoints.
4. **Test the WebSocket stream** (after starting a session)
   ```bash
   # Replace SESSION_ID with the value returned by POST /api/v1/sessions
   websocat ws://localhost:8000/api/v1/sessions/SESSION_ID/stream
   ```
   Each `POST /api/v1/sessions/{id}/moves` call now pushes a JSON envelope such as:
   ```json
   {
     "type": "engine_move",
     "payload": {
       "uci": "e7e5",
       "engine_eval_cp": 35,
       "exploit_confidence": 0.72,
       "best_line": ["e7e5", "d2d4", "c5d4"],
       "clocks": {"player_ms": 300000, "engine_ms": 300000},
       "game_state": {"fen": "...", "move_number": 2, "turn": "white"},
       "opponent_profile": {...},
       "explanation": {...}
     }
   }
   ```
   *Note:* Move legality, castling, and en passant are now handled by python-chess to keep server state authoritative.

> **Persistence.** By default the API uses a local SQLite file (`chessica.db`). Set `DATABASE_URL=postgresql://user:pass@host/dbname` to run against Postgres. Redis caching is enabled automatically when `REDIS_URL=redis://localhost:6379/0` (falls back to in-process TTL cache otherwise). Engine events stream into the `engine_events` table for later analytics.
>
> **Engine defaults.** Engine moves now come from Stockfish. Tune the global defaults with `ENGINE_DEFAULT_DEPTH` or override per session using the difficulty dropdown/field. Each preset maps to Stockfish `Skill Level`, `UCI_Elo`, and a sub-second move time so responses stay <1 s.
>
> **Schema note.** If you created `chessica.db` before the difficulty update, delete it (or run the appropriate `ALTER TABLE sessions ADD COLUMN ...`) so the new columns (`difficulty`, `engine_depth`, `engine_rating`) exist before restarting the server.

> **Persistence.** By default the API uses a local SQLite file (`chessica.db`). Set `DATABASE_URL=postgresql://user:pass@host/dbname` to run against Postgres. Redis caching is enabled automatically when `REDIS_URL=redis://localhost:6379/0` (falls back to in-process TTL cache otherwise). Engine events stream into the `engine_events` table for later analytics.
> **Schema note.** If you created `chessica.db` before the difficulty update, delete it (or run `ALTER TABLE sessions ADD COLUMN difficulty TEXT ...`, etc.) so the new columns (`difficulty`, `engine_depth`, `engine_rating`) exist before restarting the server.
> **Engine defaults.** Tune the backend search depth globally with `ENGINE_DEFAULT_DEPTH` (default 3); per-session overrides are available via the `engine_depth` field or the frontend dropdown.

### 14.3 Frontend Prototype
The `frontend/` directory contains a lightweight static UI that consumes the backend API.

1. Start the backend server on `localhost:8000`.
2. Serve the static files (any HTTP server works):
   ```bash
   cd frontend
   python3 -m http.server 4173
   ```
3. Open `http://localhost:4173` and use the controls to create a session. Choose an engine strength (depth 2–5), drag pieces directly on the board (or fall back to the UCI input) to submit moves, then read the explanations and stream output in real time.
4. Use the **Session Analytics** panel’s “Refresh” button (or make moves) to fetch aggregated telemetry via `GET /api/v1/analytics/sessions/{id}/events`.

> This prototype avoids build tooling; React/Vite can replace it later if desired.
> The board uses [`chessboard-element`](https://github.com/justinfagnani/chessboard-element) and [`chess.js`](https://github.com/jhlywa/chess.js) via CDN, so ensure the frontend machine has internet access the first time it loads.

### 14.4 Next Development Targets
1. Replace the mock engine/explanation pipeline with the real policy/value service + opponent model (GPU-backed inference + MCTS tie-in).
2. Move engine move generation into background jobs (Redis queue / task workers) to scale under load and decouple search latency from API threads.
3. Build analytics endpoints/dashboards that consume `engine_events` (win-rate curves, exploit gain over time, motif-frequency heatmaps).
