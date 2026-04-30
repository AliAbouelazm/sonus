"""
Discord integration — sends messages to a channel via webhook.
No bot token needed; just a webhook URL from Server Settings → Integrations.
"""
import logging
import httpx

from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)


class DiscordIntegration:
    async def _get_webhook_url(self) -> str:
        db_config = await get_integration_config("discord")
        return ((db_config or {}).get("webhook_url") or "").strip()

    async def send_message(self, content: str, username: str = "Sonus") -> dict:
        webhook_url = await self._get_webhook_url()
        if not webhook_url:
            return {"error": "Discord not connected. Add it on the Integrations page."}

        payload = {"content": content, "username": username}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
                # 204 No Content = success for Discord webhooks
                if resp.status_code in (200, 204):
                    return {"ok": True, "message": f"Sent to Discord: {content}"}
                return {"error": f"Discord webhook returned {resp.status_code}: {resp.text}"}
        except Exception as e:
            logger.error("Discord send failed: %s", e)
            return {"error": f"Could not send Discord message: {str(e)}"}

    async def send_embed(self, title: str, description: str, color: int = 0x5865F2) -> dict:
        webhook_url = await self._get_webhook_url()
        if not webhook_url:
            return {"error": "Discord not connected. Add it on the Integrations page."}

        payload = {
            "username": "Sonus",
            "embeds": [{"title": title, "description": description, "color": color}],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code in (200, 204):
                    return {"ok": True}
                return {"error": f"Discord webhook returned {resp.status_code}: {resp.text}"}
        except Exception as e:
            logger.error("Discord embed send failed: %s", e)
            return {"error": f"Could not send Discord message: {str(e)}"}
