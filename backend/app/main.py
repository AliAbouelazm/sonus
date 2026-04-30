import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.agent.core import Agent
from backend.app.agent.tools import ToolExecutor
from backend.app.api.routes import router as api_router
from backend.app.api.websocket import websocket_endpoint, ws_manager
from backend.app.config import settings
from backend.app.devices.manager import DeviceManager
from backend.app.integrations.canvas_ics import CanvasICSIntegration
from backend.app.integrations.google_calendar import GoogleCalendarIntegration
from backend.app.integrations.fatsecret import FatSecretIntegration
from backend.app.integrations.gmail import GmailIntegration
from backend.app.integrations.google_tasks import GoogleTasksIntegration
from backend.app.integrations.ntfy import NtfyIntegration
from backend.app.integrations.discord import DiscordIntegration
from backend.app.integrations.twilio import TwilioIntegration
from backend.app.integrations.telegram import TelegramIntegration
from backend.app.integrations.spotify import SpotifyIntegration
from backend.app.integrations.weather import WeatherIntegration
from backend.app.memory.database import init_db
from backend.app.memory.store import MemoryStore
from backend.app.scheduler.scheduler import SonusScheduler
from backend.app.intelligence.observation_logger import ObservationLogger
from backend.app.intelligence.outcome_tracker import OutcomeTracker
from backend.app.intelligence.confidence import ConfidenceSystem
from backend.app.intelligence.biometric_loop import BiometricLoop
from backend.app.intelligence.thinking_loop import ThinkingLoop
from backend.app.intelligence.experiment_engine import ExperimentEngine
from backend.app.intelligence.local_models import LocalModelTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Sonus...")

    await init_db()
    logger.info("Database initialized")

    memory_store = MemoryStore()
    device_manager = DeviceManager()

    # Sync hardware devices from connected integrations
    integration_configs = await memory_store.get_integration_configs()
    device_manager.sync_from_integrations(integration_configs)

    persisted = await memory_store.load_device_states()
    if persisted:
        device_manager.load_states(persisted)
        logger.info("Loaded persisted device states")

    weather = WeatherIntegration()
    calendar = GoogleCalendarIntegration()
    canvas = CanvasICSIntegration()
    fatsecret = FatSecretIntegration()
    spotify = SpotifyIntegration()
    tasks = GoogleTasksIntegration(calendar)
    gmail = GmailIntegration(calendar)
    ntfy = NtfyIntegration()
    discord = DiscordIntegration()
    twilio = TwilioIntegration()
    telegram = TelegramIntegration()

    tool_executor = ToolExecutor(
        device_manager=device_manager,
        memory_store=memory_store,
        weather_integration=weather,
        calendar_integration=calendar,
        canvas_integration=canvas,
        fatsecret_integration=fatsecret,
        spotify_integration=spotify,
        tasks_integration=tasks,
        gmail_integration=gmail,
        ntfy_integration=ntfy,
        discord_integration=discord,
        twilio_integration=twilio,
        telegram_integration=telegram,
    )

    agent = Agent(tool_executor)

    history = await memory_store.get_conversation_history(limit=20)
    for msg in history:
        agent.conversation_history.append({"role": msg["role"], "content": msg["content"]})

    async def on_device_state_change(device_id: str, device_info: dict[str, Any]) -> None:
        await ws_manager.broadcast({
            "type": "device_update",
            "device_id": device_id,
            "state": device_info["state"],
            "device_type": device_info["device_type"],
        })

    device_manager.set_on_state_change(on_device_state_change)

    scheduler = SonusScheduler(memory_store)

    async def on_reminder(reminder: dict[str, Any]) -> None:
        await ws_manager.broadcast({
            "type": "reminder",
            "title": reminder["title"],
            "description": reminder.get("description", ""),
        })

    scheduler.set_on_reminder(on_reminder)
    scheduler.start()

    app.state.telegram = telegram
    app.state.agent = agent
    app.state.device_manager = device_manager
    app.state.memory_store = memory_store
    app.state.store = memory_store
    app.state.scheduler = scheduler
    app.state.calendar = calendar
    app.state.spotify = spotify
    app.state.fatsecret = fatsecret
    app.state.mode = "demo"
    agent.mode = "demo"

    obs_logger = ObservationLogger(app.state)
    outcome_tracker = OutcomeTracker(app.state)
    confidence_system = ConfidenceSystem(app.state)
    experiment_engine = ExperimentEngine(app.state, device_manager)
    local_model_trainer = LocalModelTrainer(app.state)

    biometric_loop = BiometricLoop(app.state, device_manager, obs_logger, outcome_tracker, ws_manager)
    thinking_loop = ThinkingLoop(app.state, agent, device_manager, obs_logger, confidence_system, ws_manager)

    app.state.obs_logger = obs_logger
    app.state.outcome_tracker = outcome_tracker
    app.state.confidence_system = confidence_system
    app.state.experiment_engine = experiment_engine
    app.state.local_model_trainer = local_model_trainer
    app.state.biometric_loop = biometric_loop
    app.state.thinking_loop = thinking_loop

    telegram.start_polling(agent, memory_store)

    logger.info("Sonus is ready! Open http://127.0.0.1:%d", settings.port)

    yield

    await biometric_loop.stop()
    await thinking_loop.stop()
    await telegram.stop_polling()
    scheduler.stop()
    await agent.llm.close()
    logger.info("Sonus shut down.")


app = FastAPI(title="Sonus", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def ws_route(websocket: WebSocket) -> None:
    await websocket_endpoint(
        websocket,
        agent=app.state.agent,
        device_manager=app.state.device_manager,
        memory_store=app.state.memory_store,
    )


# Serve React build if available, otherwise fall back to legacy vanilla frontend
_base = os.path.dirname(__file__)
_react_dist = os.path.join(_base, "..", "..", "frontend-react", "dist")
_legacy_frontend = os.path.join(_base, "..", "..", "frontend")

if os.path.isdir(_react_dist) and os.path.isfile(os.path.join(_react_dist, "index.html")):
    app.mount("/", StaticFiles(directory=_react_dist, html=True), name="frontend")
elif os.path.isdir(_legacy_frontend):
    app.mount("/", StaticFiles(directory=_legacy_frontend, html=True), name="frontend")
