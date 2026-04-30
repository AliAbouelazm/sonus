"""
Telegram Bot integration — send messages to the user and receive messages from them.
Uses the Telegram Bot API with long-polling (no public URL needed).
"""
import asyncio
import logging
import httpx
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot"


class TelegramIntegration:
    def __init__(self) -> None:
        self._poll_task: asyncio.Task | None = None
        self._offset: int = 0

    async def _get_config(self) -> dict:
        return await get_integration_config("telegram") or {}

    async def _get_bot_token(self) -> str:
        config = await self._get_config()
        return config.get("bot_token", "").strip()

    async def _get_chat_id(self) -> str:
        config = await self._get_config()
        return str(config.get("chat_id", "")).strip()

    async def send_message(self, text: str) -> dict:
        bot_token = await self._get_bot_token()
        chat_id = await self._get_chat_id()

        if not bot_token:
            return {"error": "Telegram not connected. Add it on the Integrations page."}
        if not chat_id:
            return {"error": "Telegram: no chat ID configured. Send /start to your bot first, then re-save the integration."}

        url = f"{TELEGRAM_API}{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if data.get("ok"):
                    return {"ok": True, "message": f"Sent to Telegram: {text}"}
                return {"error": f"Telegram error: {data.get('description', 'unknown')}"}
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return {"error": f"Could not send Telegram message: {str(e)}"}

    async def _get_updates(self, bot_token: str) -> list:
        """Long-poll Telegram for new messages (30s timeout)."""
        url = f"{TELEGRAM_API}{bot_token}/getUpdates"
        params = {"timeout": 30, "offset": self._offset, "allowed_updates": ["message"]}
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
        except Exception as e:
            logger.debug("Telegram getUpdates error: %s", e)
        return []

    def start_polling(self, agent: object, memory_store: object) -> None:
        """Start the background polling loop."""
        if self._poll_task and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_loop(agent, memory_store))
        logger.info("Telegram polling started")

    async def stop_polling(self) -> None:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram polling stopped")

    async def _poll_loop(self, agent: object, memory_store: object) -> None:
        logger.info("Telegram poll loop running")
        while True:
            try:
                bot_token = await self._get_bot_token()
                if not bot_token:
                    await asyncio.sleep(10)
                    continue

                updates = await self._get_updates(bot_token)
                for update in updates:
                    self._offset = update["update_id"] + 1
                    await self._handle_update(update, agent, memory_store)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Telegram poll loop error: %s", e)
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict, agent: object, memory_store: object) -> None:
        message = update.get("message")
        if not message:
            return

        text = (message.get("text") or "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not text or not chat_id:
            return

        # Only respond to the configured chat ID
        configured_chat_id = await self._get_chat_id()
        if configured_chat_id and chat_id != configured_chat_id:
            logger.debug("Ignoring Telegram message from unknown chat %s", chat_id)
            return

        if text == "/start":
            await self._reply(chat_id, "Hey! I'm Sonus, your smart home assistant. What can I do for you?")
            return

        try:
            await memory_store.save_conversation("user", text)
            reply = await agent.process_message(text)
            await memory_store.save_conversation("assistant", reply)
            # Strip markdown bold/italic that Telegram might not render well
            await self._reply(chat_id, reply)
        except Exception as e:
            logger.error("Telegram message handling error: %s", e)
            await self._reply(chat_id, "Sorry, something went wrong on my end.")

    async def _reply(self, chat_id: str, text: str) -> None:
        bot_token = await self._get_bot_token()
        if not bot_token:
            return
        url = f"{TELEGRAM_API}{bot_token}/sendMessage"
        # Telegram Markdown can fail on some chars — use plain text for replies
        payload = {"chat_id": chat_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.error("Telegram reply failed: %s", e)

    async def get_me(self) -> dict:
        """Verify the bot token is valid."""
        bot_token = await self._get_bot_token()
        if not bot_token:
            return {"error": "No bot token."}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{TELEGRAM_API}{bot_token}/getMe")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}
