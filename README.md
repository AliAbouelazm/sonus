# Sonus — Agentic Smart Home Assistant

> **Python · FastAPI · React · scikit-learn · WebSockets · OpenAI/Anthropic APIs · SQLite**

Sonus is an autonomous LLM-powered assistant that learns your environment and acts without being explicitly asked. It connects to your real devices and services (wearables, smart home, calendar, Spotify), reasons about your context, and executes multi-step routines on your behalf. A confidence system learns from your feedback over time, and local scikit-learn models train on your own biometric data to predict stress and sleep.

**Example:**
> "Set me up for studying."
> Sonus checks your calendar, dims the lights to cool white, turns the AC to 70°F, puts Spotify on lo-fi, and remembers you like the fan on while you work.

---

## Modes

| Mode | What it does |
|------|-------------|
| **Demo** | Responds to chat, executes commands, no background loops running |
| **Train** | Everything in Demo + two autonomous background loops that watch your biometrics, learn your patterns, and act without being asked |

Switch modes with the toggle in the UI or `POST /api/mode {"mode": "train"}`.

---

## Features

- **LLM agent** — reasons about context, time, calendar, weather, and your history
- **Integrations page** — drag integrations onto a brain diagram to connect them
- **Train mode** — biometric loop watches wearables every 30–60s; thinking loop checks learned patterns every 2–5 min
- **Confidence system** — patterns gain/lose confidence from your feedback (approve, undo, never, etc.)
- **Experiment engine** — A/B tests variables in your environment (e.g. which lighting reduces stress most)
- **Local ML models** — trains a stress predictor and sleep time predictor on your data
- **Persistent memory** — SQLite for preferences, patterns, conversations, biometrics, device states
- **Real-time updates** — WebSocket for live device state, chat, and autonomous action notifications
- **React frontend** — integrations brain page + chat page

---

## Integrations

### Software
| Integration | What you need |
|-------------|---------------|
| Google Calendar | OAuth (click Connect) or ICS feed URL |
| Gmail | OAuth — same Google sign-in as Calendar |
| Google Tasks | OAuth — same Google sign-in |
| Canvas LMS | ICS feed URL from Canvas Settings → Calendar Feed |
| Weather | Free OpenWeatherMap API key |
| Spotify | OAuth (click Connect) |
| FatSecret | Consumer Key + Consumer Secret from platform.fatsecret.com |
| Notion | Internal Integration Token from notion.so/my-integrations |
| Todoist | API Token from Todoist Settings → Integrations |

### Hardware (Simulated, Home Assistant, or native APIs)
| Integration | Controls |
|-------------|---------|
| Smart Light | Brightness, color temperature |
| Smart Lock | Lock / unlock |
| Smart Fan | On/off, speed |
| Thermostat / AC | Temperature, mode |

### Wearables (feed the biometric loop in Train mode)
| Integration | Data |
|-------------|------|
| Garmin Connect | Heart rate, stress, body battery, HRV, steps, sleep |
| Whoop | Recovery, strain, HRV, sleep performance |
| Oura Ring | Readiness, sleep score, activity |
| Apple Health | HR, HRV, steps, sleep (via Shortcuts webhook) |

### Communication
| Integration | How to get it |
|-------------|---------------|
| ntfy | Free — install ntfy app, pick any topic name |
| Telegram | Create a bot via @BotFather, paste token + chat ID |
| Discord | Webhook URL from Server Settings → Integrations |
| Twilio SMS | Account SID + Auth Token from console.twilio.com |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for React frontend dev server)
- TAMU Chat or OpenAI-compatible API key

### 1. Backend

```bash
pip install -r backend/requirements.txt
cp backend/.env.example .env
# Edit .env — set AI_API_KEY at minimum
python run.py
# → http://localhost:8000
```

### 2. Frontend dev server (optional, hot reload)

```bash
cd frontend-react
npm install
npm run dev
# → http://localhost:5173  (proxies /api and /ws to backend)
```

### 3. Production build (served by FastAPI)

```bash
cd frontend-react && npm run build
# FastAPI now serves the app at http://localhost:8000
```

---

## .env Reference

```env
# Required
AI_API_KEY=your_key_here
AI_BASE_URL=https://chat-api.tamu.ai/api   # or https://api.openai.com/v1
AI_MODEL=protected.gpt-4o

# Google OAuth (Calendar, Gmail, Tasks — one sign-in covers all three)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/gcal/callback

# Spotify OAuth
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/spotify/callback

# Optional fallbacks (can also be set in the UI)
WEATHER_API_KEY=
WEATHER_CITY=College Station
CANVAS_ICS_URL=
NTFY_TOPIC=

USER_NAME=User
DAILY_TOKEN_BUDGET=0
DATABASE_URL=sqlite+aiosqlite:///./sonus.db
HOST=0.0.0.0
PORT=8000
```

---

## Architecture

```
sonus/
├── run.py                           # Entry point
├── pytest.ini
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py                  # FastAPI app, lifespan, state init
│       ├── config.py                # Pydantic settings
│       ├── agent/
│       │   ├── core.py              # LLM agent (tool-calling loop)
│       │   ├── tools.py             # Tool definitions + executors
│       │   └── prompts.py           # System prompt
│       ├── integrations/            # One file per service
│       │   ├── fatsecret.py         # OAuth 1.0a food diary
│       │   ├── google_calendar.py
│       │   ├── spotify.py
│       │   ├── garmin.py
│       │   ├── whoop.py
│       │   └── ...
│       ├── intelligence/            # Train mode autonomous systems
│       │   ├── biometric_loop.py    # Reads wearables, detects deviations, applies interventions
│       │   ├── thinking_loop.py     # Checks patterns, auto-executes or suggests
│       │   ├── confidence.py        # Pattern confidence scoring + decay
│       │   ├── experiment_engine.py # A/B test variables in your environment
│       │   ├── local_models.py      # scikit-learn stress + sleep predictors
│       │   ├── observation_logger.py
│       │   └── outcome_tracker.py
│       ├── memory/
│       │   ├── models.py            # SQLAlchemy models (16 tables)
│       │   ├── database.py          # Async SQLite engine + get_db()
│       │   └── store.py             # High-level memory helpers
│       ├── devices/                 # Real + simulated device drivers
│       └── api/
│           ├── routes.py            # REST endpoints
│           └── websocket.py         # WS manager + chat handler
├── frontend-react/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── IntegrationsPage.jsx # Brain diagram + drag-and-drop
│   │   │   └── ChatPage.jsx
│   │   ├── components/
│   │   │   ├── Brain.jsx            # SVG orbit layout + connection lines
│   │   │   ├── CategoryPanel.jsx
│   │   │   └── ConfigModal.jsx      # Integration setup form
│   │   └── data/
│   │       └── integrations.js      # Integration registry
│   └── package.json
├── frontend/                        # Legacy vanilla JS (fallback)
└── tests/
    └── train_mode/                  # Isolated test suite (47 tests)
        ├── conftest.py              # In-memory DB fixtures
        ├── mock_wearables.py
        ├── mock_devices.py
        ├── test_biometric.py
        ├── test_thinking.py
        ├── test_confidence.py
        ├── test_scenarios.py        # few vs many integrations
        └── simulate.py              # CLI scenario runner
```

---

## Testing Train Mode

```bash
# Run all tests (isolated DB, no real devices or API calls)
/opt/homebrew/bin/python3 -m pytest tests/train_mode/ -v -s -W ignore::DeprecationWarning

# Save output with live WS messages
/opt/homebrew/bin/python3 -m pytest tests/train_mode/ -v -s 2>&1 | tee tests/train_mode/last_run.log

# CLI simulation (never touches sonus.db)
/opt/homebrew/bin/python3 tests/train_mode/simulate.py --mode few --scenario stress
/opt/homebrew/bin/python3 tests/train_mode/simulate.py --mode many --scenario hr
```

---

## Train Mode: How It Works

### Biometric Loop (runs every 30–60s in Train mode)
1. Polls all connected wearables and merges readings
2. Maintains rolling EMA baselines per metric (stress, HR, body battery, HRV, steps)
3. Detects deviations beyond thresholds (stress +20, HR +15, battery drain >15%/hr)
4. Looks up intervention effectiveness for that deviation type:
   - **≥ 0.75** → auto-applies intervention (dims lights, turns on AC/fan)
   - **0.50–0.74** → asks you first via WebSocket
   - **< 0.50** → logs only, no action
5. Schedules an outcome check 10 minutes later; updates effectiveness score

### Thinking Loop (runs every 2–5 min in Train mode)
1. Loads all active patterns from DB
2. Checks each pattern's conditions (time range, day type, specific days)
3. Skips patterns you previously denied in a similar time context (±1 hour)
4. Acts based on confidence:
   - **≥ 0.85** → executes device actions, broadcasts `autonomous_action` via WS
   - **0.50–0.84** → broadcasts `pattern_suggestion` via WS (no device action)
   - **< 0.50** → ignored
5. Decays all pattern confidence by 1%/week when not reinforced

### Confidence Signals

| Signal | Trigger | Confidence Δ |
|--------|---------|-------------|
| `approve` | "Yes, do that" | +0.08 |
| `always` | "Always do this" | +0.25 |
| `passive_approve` | Pattern ran, no undo | +0.02 |
| `user_did_it` | You did it yourself | +0.05 |
| `no` | "No" | -0.12 |
| `not_now` | "Not right now" | -0.03 |
| `undo_fast` | Undo within 2 min | -0.25 |
| `undo_slow` | Undo after 2 min | -0.15 |
| `never` | "Never suggest this" | -0.40 |
| `did_opposite` | You did the opposite | -0.10 |
