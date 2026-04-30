import logging
from typing import Any

import httpx

from backend.app.config import settings
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)


class NtfyIntegration:
    """Send push notifications to your phone via ntfy.sh (free, no account needed)."""

    async def send(
        self,
        message: str,
        title: str = "Sonus",
        priority: str = "default",
        tags: str = "",
    ) -> Any:
        db_config = await get_integration_config("ntfy")
        topic = (db_config or {}).get("ntfy_topic") or settings.ntfy_topic
        if not topic:
            return {"error": "ntfy not connected. Add it on the Integrations page."}

        try:
            headers: dict[str, str] = {
                "Title": title,
                "Priority": priority,
            }
            if tags:
                headers["Tags"] = tags

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://ntfy.sh/{topic}",
                    content=message,
                    headers=headers,
                )
                response.raise_for_status()

            return {"status": "sent", "message": message}
        except Exception as e:
            logger.exception("Failed to send ntfy notification")
            return {"error": f"Failed to send notification: {str(e)}"}
