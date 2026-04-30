import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasting."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_to(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            logger.exception("Failed to send message to WebSocket")


ws_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, agent: Any, device_manager: Any, memory_store: Any) -> None:
    await ws_manager.connect(websocket)

    all_states = device_manager.get_all_states()
    for device_id, device_info in all_states.items():
        await ws_manager.send_to(websocket, {
            "type": "device_update",
            "device_id": device_id,
            "state": device_info["state"],
            "device_type": device_info["device_type"],
        })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_to(websocket, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws_manager.send_to(websocket, {"type": "pong"})
                continue

            if msg_type == "set_disabled_devices":
                disabled = data.get("devices", [])
                device_manager.set_disabled(disabled)
                continue

            if msg_type == "chat":
                content = data.get("content", "").strip()
                if not content:
                    continue

                await ws_manager.send_to(websocket, {"type": "chat_start"})

                await memory_store.save_conversation("user", content)

                async def on_tool_call(tool_name: str, params: dict) -> None:
                    await ws_manager.send_to(websocket, {
                        "type": "tool_call",
                        "tool": tool_name,
                        "params": params,
                    })

                try:
                    response = await agent.process_message(content, on_tool_call=on_tool_call)
                except Exception as e:
                    logger.exception("Agent processing error")
                    response = f"I ran into an issue processing that: {str(e)}"

                await memory_store.save_conversation("assistant", response)

                await ws_manager.send_to(websocket, {
                    "type": "chat_complete",
                    "content": response,
                })

                states = device_manager.export_states()
                device_types = {
                    did: dev.device_type
                    for did in states
                    if (dev := device_manager.get_device(did)) is not None
                }
                await memory_store.save_device_states(states, device_types)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error")
        ws_manager.disconnect(websocket)
