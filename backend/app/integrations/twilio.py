"""
Twilio integration — sends SMS text messages.
"""
import logging
import httpx
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)


class TwilioIntegration:
    async def _get_config(self) -> dict:
        return await get_integration_config("twilio") or {}

    async def send_sms(self, message: str) -> dict:
        config = await self._get_config()
        account_sid = config.get("account_sid", "").strip()
        auth_token = config.get("auth_token", "").strip()
        to_number = config.get("phone_number", "").strip()
        from_number = config.get("from_number", "").strip()

        if not account_sid or not auth_token:
            return {"error": "Twilio not connected. Add it on the Integrations page."}
        if not to_number:
            return {"error": "Twilio: no destination phone number configured."}
        if not from_number:
            from_number = "+15005550006"  # Twilio test number fallback

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = {"To": to_number, "From": from_number, "Body": message}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, data=payload, auth=(account_sid, auth_token))
                if resp.status_code in (200, 201):
                    return {"ok": True, "message": f"SMS sent: {message}"}
                return {"error": f"Twilio returned {resp.status_code}: {resp.text}"}
        except Exception as e:
            logger.error("Twilio send failed: %s", e)
            return {"error": f"Could not send SMS: {str(e)}"}
