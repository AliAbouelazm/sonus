import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str


class ConnectIntegrationRequest(BaseModel):
    integration_id: str
    instance_id: str
    display_name: str = ""
    config: dict = {}


class ModeRequest(BaseModel):
    mode: str  # "active" or "demo"


@router.get("/mode")
async def get_mode(request: Request) -> dict[str, str]:
    return {"mode": getattr(request.app.state, "mode", "demo")}


@router.post("/mode")
async def set_mode(req: ModeRequest, request: Request) -> dict[str, str]:
    if req.mode not in ("active", "demo"):
        raise HTTPException(status_code=422, detail=f"Invalid mode '{req.mode}'. Must be 'active' or 'demo'.")
    previous_mode = getattr(request.app.state, "mode", "demo")
    request.app.state.mode = req.mode
    agent = request.app.state.agent
    agent.mode = req.mode

    biometric_loop = getattr(request.app.state, "biometric_loop", None)
    thinking_loop = getattr(request.app.state, "thinking_loop", None)

    if req.mode == "active" and previous_mode != "active":
        if biometric_loop:
            await biometric_loop.start()
        if thinking_loop:
            await thinking_loop.start()
    elif req.mode == "demo" and previous_mode == "active":
        if biometric_loop:
            await biometric_loop.stop()
        if thinking_loop:
            await thinking_loop.stop()

    logger.info("Sonus mode changed to: %s", req.mode)
    return {"mode": req.mode}


@router.post("/telegram/webhook")
async def telegram_webhook(payload: dict, request: Request) -> dict:
    """Receive incoming messages from Telegram and route them through the agent."""
    try:
        message = payload.get("message") or payload.get("edited_message")
        if not message:
            return {"ok": True}

        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))

        if not text or not chat_id:
            return {"ok": True}

        # Ignore bot commands other than /start
        if text.startswith("/") and text != "/start":
            return {"ok": True}

        if text == "/start":
            reply = "Hey! I'm Sonus, your smart home assistant. How can I help?"
        else:
            agent = request.app.state.agent
            memory_store = request.app.state.memory_store
            await memory_store.save_conversation("user", text)
            reply = await agent.process_message(text)
            await memory_store.save_conversation("assistant", reply)

        telegram = getattr(request.app.state, "telegram", None)
        if telegram:
            await telegram.send_message(reply)

    except Exception:
        logger.exception("Telegram webhook error")

    return {"ok": True}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    agent = request.app.state.agent
    memory_store = request.app.state.memory_store

    await memory_store.save_conversation("user", req.message)

    response = await agent.process_message(req.message)

    await memory_store.save_conversation("assistant", response)

    states = request.app.state.device_manager.export_states()
    device_manager = request.app.state.device_manager
    device_types = {
        did: dev.device_type
        for did in states
        if (dev := device_manager.get_device(did)) is not None
    }
    await memory_store.save_device_states(states, device_types)

    return ChatResponse(response=response)


@router.get("/devices")
async def get_devices(request: Request) -> dict[str, Any]:
    return request.app.state.device_manager.get_all_states()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/token-usage")
async def token_usage(request: Request) -> dict[str, Any]:
    agent = request.app.state.agent
    return agent.llm.token_tracker.get_stats()


@router.get("/integrations")
async def list_integrations(request: Request) -> dict[str, Any]:
    memory_store = request.app.state.memory_store
    configs = await memory_store.get_integration_configs()
    return {"integrations": configs}


@router.post("/integrations/connect")
async def connect_integration(req: ConnectIntegrationRequest, request: Request) -> dict[str, Any]:
    from backend.app.api.websocket import ws_manager
    memory_store = request.app.state.memory_store
    device_manager = request.app.state.device_manager
    result = await memory_store.save_integration_config(
        req.integration_id, req.instance_id, req.config, req.display_name
    )
    # Sync hardware devices with updated integrations
    configs = await memory_store.get_integration_configs()
    device_manager.sync_from_integrations(configs)
    await ws_manager.broadcast({
        "type": "integration_update",
        "action": "connected",
        "integration_id": req.integration_id,
        "display_name": req.display_name or req.integration_id,
    })
    return result


@router.delete("/integrations/{instance_id}")
async def disconnect_integration(instance_id: str, request: Request) -> dict[str, Any]:
    from backend.app.api.websocket import ws_manager
    memory_store = request.app.state.memory_store
    device_manager = request.app.state.device_manager
    # Fetch info before deleting so we can broadcast the name
    configs = await memory_store.get_integration_configs()
    target = next((c for c in configs if c["instance_id"] == instance_id), None)
    success = await memory_store.delete_integration_config(instance_id)
    if success:
        # Sync hardware devices after removal
        updated_configs = await memory_store.get_integration_configs()
        device_manager.sync_from_integrations(updated_configs)
        if target:
            await ws_manager.broadcast({
                "type": "integration_update",
                "action": "disconnected",
                "integration_id": target["integration_id"],
                "display_name": target.get("display_name") or target["integration_id"],
            })
    return {"success": success}


@router.get("/intelligence/patterns")
async def get_patterns(request: Request):
    confidence_system = request.app.state.confidence_system
    return {"patterns": await confidence_system.list_patterns()}


@router.get("/intelligence/observations")
async def get_observations(request: Request):
    store = request.app.state.store
    return {"observations": await store.get_observations(limit=100)}


@router.get("/intelligence/experiments")
async def get_experiments(request: Request):
    engine = request.app.state.experiment_engine
    return {"experiments": await engine.list_experiments()}


@router.post("/intelligence/experiments")
async def create_experiment(request: Request):
    data = await request.json()
    engine = request.app.state.experiment_engine
    exp = await engine.create_experiment(
        name=data["name"],
        description=data.get("description", ""),
        variable=data["variable"],
        values_to_test=data["values_to_test"],
        outcome_metric=data["outcome_metric"],
        runs_per_value=data.get("runs_per_value", 3),
    )
    return exp


@router.post("/intelligence/patterns/{pattern_id}/feedback")
async def pattern_feedback(pattern_id: int, request: Request):
    data = await request.json()
    signal = data.get("signal")  # "approve", "no", "always", "never", "not_now"
    context = data.get("context", {})
    confidence_system = request.app.state.confidence_system
    await confidence_system.adjust(pattern_id, signal, context)
    return {"ok": True}


@router.post("/intelligence/train")
async def trigger_training(request: Request):
    """Manually trigger local model training."""
    if request.app.state.mode != "train":
        return {"error": "Only available in TRAIN mode"}
    trainer = request.app.state.local_model_trainer
    await trainer.train_all()
    status = await trainer.get_model_status()
    return {"ok": True, "models": status}


class AdminResetRequest(BaseModel):
    confirm: bool = False


@router.post("/admin/reset")
async def admin_reset(req: AdminResetRequest, request: Request) -> dict[str, Any]:
    """Clear all integration configs, memories, conversations, and agent history."""
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Must send {\"confirm\": true} to reset.")

    from backend.app.api.websocket import ws_manager
    from backend.app.memory.database import async_session
    from backend.app.memory.models import Conversation, IntegrationConfig, Memory, Reminder

    async with async_session() as session:
        await session.execute(delete(IntegrationConfig))
        await session.execute(delete(Memory))
        await session.execute(delete(Conversation))
        await session.execute(delete(Reminder))
        await session.commit()

    agent = request.app.state.agent
    agent.clear_history()

    await ws_manager.broadcast({"type": "reset"})
    logger.warning("Sonus full reset executed: all data cleared.")
    return {"success": True}


@router.get("/gcal/login")
async def gcal_login(request: Request) -> Any:
    gcal = request.app.state.calendar
    # Load credentials saved via the UI (takes priority over .env)
    memory_store = request.app.state.memory_store
    configs = await memory_store.get_integration_configs()
    gcal_config = next((c for c in configs if c["integration_id"] == "google_calendar"), None)
    if gcal_config:
        cfg = gcal_config.get("config", {})
        if cfg.get("client_id") or cfg.get("client_secret"):
            gcal.set_oauth_credentials(cfg.get("client_id", ""), cfg.get("client_secret", ""))
    url = gcal.get_auth_url()
    if not url:
        return HTMLResponse(
            "<h2>Google Calendar not configured</h2>"
            "<p>Enter your Google Client ID and Client Secret in the Sonus Integrations page, "
            "or set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env</p>",
            status_code=400,
        )
    return RedirectResponse(url)


@router.get("/gcal/callback")
async def gcal_callback(request: Request, code: str = "") -> Any:
    if not code:
        return HTMLResponse("<h2>Missing auth code</h2>", status_code=400)
    gcal = request.app.state.calendar
    success = gcal.handle_callback(code)
    if success:
        return HTMLResponse(
            "<h2>Google Calendar connected!</h2>"
            "<p>You can now create, edit, and delete events. Close this tab and go back to Sonus.</p>"
            '<script>setTimeout(()=>window.close(),2000)</script>'
        )
    return HTMLResponse("<h2>Google Calendar auth failed</h2><p>Check server logs.</p>", status_code=500)


@router.get("/gcal/status")
async def gcal_status(request: Request) -> dict[str, Any]:
    gcal = request.app.state.calendar
    return {
        "oauth_configured": gcal._oauth_configured(),
        "authenticated": gcal.is_authenticated(),
    }


@router.get("/spotify/login")
async def spotify_login(request: Request) -> Any:
    spotify = request.app.state.spotify
    # Load credentials saved via the UI (takes priority over .env)
    memory_store = request.app.state.memory_store
    configs = await memory_store.get_integration_configs()
    spotify_config = next((c for c in configs if c["integration_id"] == "spotify"), None)
    if spotify_config:
        cfg = spotify_config.get("config", {})
        if cfg.get("client_id") or cfg.get("client_secret"):
            spotify.set_oauth_credentials(cfg.get("client_id", ""), cfg.get("client_secret", ""))
    url = spotify.get_auth_url()
    if not url:
        return HTMLResponse(
            "<h2>Spotify not configured</h2>"
            "<p>Enter your Spotify Client ID and Client Secret in the Sonus Integrations page, "
            "or set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env</p>",
            status_code=400,
        )
    return RedirectResponse(url)


@router.get("/spotify/callback")
async def spotify_callback(request: Request, code: str = "") -> Any:
    if not code:
        return HTMLResponse("<h2>Missing auth code</h2>", status_code=400)
    spotify = request.app.state.spotify
    success = spotify.handle_callback(code)
    if success:
        return HTMLResponse(
            "<h2>Spotify connected!</h2>"
            "<p>You can close this tab and go back to Sonus.</p>"
            '<script>setTimeout(()=>window.close(),2000)</script>'
        )
    return HTMLResponse("<h2>Spotify auth failed</h2><p>Check server logs.</p>", status_code=500)


@router.get("/fatsecret/status")
async def fatsecret_status(request: Request) -> dict[str, Any]:
    fatsecret = request.app.state.fatsecret
    return {
        "configured": await fatsecret._is_configured(),
        "diary_ready": await fatsecret.is_user_authenticated(),
    }


@router.get("/spotify/status")
async def spotify_status(request: Request) -> dict[str, Any]:
    spotify = request.app.state.spotify
    result: dict[str, Any] = {
        "configured": bool(spotify._is_configured()),
        "authenticated": spotify.is_authenticated(),
    }
    if result["authenticated"]:
        pb = await spotify.get_current_playback()
        if isinstance(pb, dict) and pb.get("status") in ("playing", "paused"):
            result["now_playing"] = {
                "track": pb.get("track", ""),
                "artist": pb.get("artist", ""),
                "is_playing": pb.get("status") == "playing",
                "volume": pb.get("volume"),
            }
    return result
