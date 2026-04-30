"""
FatSecret Platform API integration.

Everything uses OAuth 1.0a signed with Consumer Key + Consumer Secret.
- Food search / nutrition: 2-legged OAuth 1.0a (app-level, no user tokens)
- Food diary: OAuth 1.0a with a profile token obtained once via profile.create
  (2-legged, no browser redirect needed — tokens are stored permanently)
"""
import logging
import time
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from oauthlib.oauth1 import Client as OAuth1Client
from sqlalchemy import select

from backend.app.config import settings
from backend.app.integrations.config_helper import get_integration_config
from backend.app.memory.database import async_session
from backend.app.memory.models import IntegrationConfig

logger = logging.getLogger(__name__)

API_BASE = "https://platform.fatsecret.com/rest/server.api"


class FatSecretIntegration:
    """FatSecret via OAuth 1.0a only — one set of credentials (Consumer Key + Secret)."""

    # ── Config helpers ────────────────────────────────────────────────────

    async def _get_config(self) -> dict:
        return await get_integration_config("fatsecret") or {}

    async def _get_credentials(self) -> tuple[str, str]:
        cfg = await self._get_config()
        key = (
            cfg.get("consumer_key")
            or cfg.get("client_id")
            or settings.fatsecret_client_id
        )
        secret = (
            cfg.get("consumer_secret")
            or cfg.get("client_secret")
            or settings.fatsecret_client_secret
        )
        return key, secret

    async def _is_configured(self) -> bool:
        key, secret = await self._get_credentials()
        return bool(key and secret)

    async def _save_config_field(self, **fields: str) -> None:
        """Merge fields into the existing FatSecret config in the DB."""
        async with async_session() as session:
            result = await session.execute(
                select(IntegrationConfig).where(
                    IntegrationConfig.integration_id == "fatsecret",
                    IntegrationConfig.is_connected == True,  # noqa: E712
                )
            )
            record = result.scalar_one_or_none()
            if record:
                updated = dict(record.config or {})
                updated.update(fields)
                record.config = updated
                await session.commit()

    # ── Core OAuth 1.0a call ──────────────────────────────────────────────

    async def _call(
        self,
        method: str,
        params: Optional[dict] = None,
        user_token: str = "",
        user_secret: str = "",
    ) -> Any:
        """
        Make an OAuth 1.0a signed POST to the FatSecret REST API.
        If user_token/user_secret are provided, they're included in the signature
        (used for diary methods). Otherwise it's app-level (2-legged).
        """
        key, secret = await self._get_credentials()
        if not key:
            return {"error": "FatSecret not connected. Add your Consumer Key on the Integrations page."}

        request_params: dict[str, Any] = {"method": method, "format": "json"}
        if params:
            request_params.update(params)

        try:
            oauth_kwargs: dict[str, Any] = {"client_secret": secret}
            if user_token and user_secret:
                oauth_kwargs["resource_owner_key"] = user_token
                oauth_kwargs["resource_owner_secret"] = user_secret

            oauth = OAuth1Client(key, **oauth_kwargs)
            body_str = urlencode(request_params)
            uri, headers, signed_body = oauth.sign(
                API_BASE,
                http_method="POST",
                body=body_str,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(uri, content=signed_body, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("FatSecret API error %s: %s", e.response.status_code, e.response.text)
            return {"error": f"FatSecret API error {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            logger.error("FatSecret call failed: %s", e)
            return {"error": f"FatSecret error: {str(e)}"}

    # ── Profile / diary tokens ────────────────────────────────────────────

    async def is_user_authenticated(self) -> bool:
        cfg = await self._get_config()
        return bool(cfg.get("user_token") and cfg.get("user_token_secret"))

    async def _ensure_profile_tokens(self) -> tuple[str, str]:
        """
        Return existing profile tokens, or call profile.create to get them.
        This is automatic — no browser redirect needed.
        """
        cfg = await self._get_config()
        user_token = cfg.get("user_token", "")
        user_secret = cfg.get("user_token_secret", "")
        if user_token and user_secret:
            return user_token, user_secret

        logger.info("FatSecret: no profile tokens yet, calling profile.create...")
        data = await self._call("profile.create")
        if "error" in data:
            logger.error("FatSecret profile.create failed: %s", data)
            return "", ""

        profile = data.get("profile", {})
        new_token = profile.get("auth_token") or profile.get("oauth_token", "")
        new_secret = profile.get("auth_secret") or profile.get("oauth_token_secret", "")

        if not new_token or not new_secret:
            logger.error("FatSecret profile.create unexpected response: %s", data)
            return "", ""

        await self._save_config_field(user_token=new_token, user_token_secret=new_secret)
        logger.info("FatSecret profile tokens saved")
        return new_token, new_secret

    # ── Food search (app-level, no user tokens needed) ────────────────────

    async def search_foods(self, query: str, max_results: int = 8) -> Any:
        if not await self._is_configured():
            return {"error": "FatSecret not connected. Add it on the Integrations page."}

        data = await self._call("foods.search.v3", {
            "search_expression": query,
            "max_results": str(max_results),
        })
        if "error" in data:
            return data

        try:
            foods_list = data.get("foods_search", {}).get("results", {}).get("food", [])
            if isinstance(foods_list, dict):
                foods_list = [foods_list]

            results = []
            for food in foods_list:
                servings = food.get("servings", {}).get("serving", [])
                if isinstance(servings, dict):
                    servings = [servings]
                first = servings[0] if servings else {}
                results.append({
                    "food_id": food.get("food_id", ""),
                    "name": food.get("food_name", ""),
                    "brand": food.get("brand_name", ""),
                    "type": food.get("food_type", ""),
                    "serving_description": first.get("serving_description", ""),
                    "calories": first.get("calories", "0"),
                    "fat": first.get("fat", "0") + "g",
                    "carbs": first.get("carbohydrate", "0") + "g",
                    "protein": first.get("protein", "0") + "g",
                })
            return {"query": query, "results": results}
        except Exception as e:
            logger.exception("Error parsing FatSecret search results")
            return {"error": f"Error parsing results: {str(e)}"}

    async def get_food_details(self, food_id: str) -> Any:
        """Full nutrition breakdown including serving_id values (needed for logging)."""
        if not await self._is_configured():
            return {"error": "FatSecret not connected. Add it on the Integrations page."}

        data = await self._call("food.get.v4", {"food_id": food_id})
        if "error" in data:
            return data

        try:
            food = data.get("food", {})
            servings_data = food.get("servings", {}).get("serving", [])
            if isinstance(servings_data, dict):
                servings_data = [servings_data]

            servings = []
            for s in servings_data:
                servings.append({
                    "serving_id": s.get("serving_id", ""),
                    "description": s.get("serving_description", ""),
                    "calories": s.get("calories", "0"),
                    "fat": s.get("fat", "0") + "g",
                    "carbs": s.get("carbohydrate", "0") + "g",
                    "protein": s.get("protein", "0") + "g",
                    "fiber": s.get("fiber", "0") + "g",
                    "sodium": s.get("sodium", "0") + "mg",
                })

            return {
                "food_id": food.get("food_id", ""),
                "name": food.get("food_name", ""),
                "brand": food.get("brand_name", ""),
                "servings": servings,
            }
        except Exception as e:
            logger.exception("Error parsing FatSecret food details")
            return {"error": f"Error parsing food details: {str(e)}"}

    async def autocomplete(self, expression: str, max_results: int = 10) -> Any:
        if not await self._is_configured():
            return {"error": "FatSecret not connected. Add it on the Integrations page."}
        data = await self._call("foods.autocomplete.v2", {
            "expression": expression,
            "max_results": str(max_results),
        })
        if "error" in data:
            return data
        try:
            suggestions = data.get("suggestions", {}).get("suggestion", [])
            if isinstance(suggestions, str):
                suggestions = [suggestions]
            return {"suggestions": suggestions}
        except Exception:
            return {"suggestions": []}

    # ── Food diary ────────────────────────────────────────────────────────

    async def log_food_entry(
        self,
        food_id: str,
        serving_id: str,
        food_entry_name: str = "",
        number_of_units: float = 1.0,
        meal: str = "other",
        date_int: Optional[int] = None,
    ) -> Any:
        """Log food to diary. Profile tokens are created automatically on first use."""
        if not await self._is_configured():
            return {"error": "FatSecret not connected. Add it on the Integrations page."}

        user_token, user_secret = await self._ensure_profile_tokens()
        if not user_token:
            return {"error": "Could not create FatSecret diary profile. Check your Consumer Key/Secret."}

        if date_int is None:
            date_int = int(time.time() // 86400)

        data = await self._call(
            "food_entry.create",
            {
                "food_id": food_id,
                "serving_id": serving_id,
                "food_entry_name": food_entry_name or food_id,
                "number_of_units": str(number_of_units),
                "meal": meal.lower(),
                "date": str(date_int),
            },
            user_token=user_token,
            user_secret=user_secret,
        )
        if "error" in data:
            return data
        entry_id = data.get("food_entry_id", "")
        return {"ok": True, "food_entry_id": entry_id, "message": f"Logged to food diary (entry {entry_id})"}

    async def get_food_entries(self, date_int: Optional[int] = None) -> Any:
        """Get today's food diary entries with total calories."""
        if not await self._is_configured():
            return {"error": "FatSecret not connected. Add it on the Integrations page."}

        user_token, user_secret = await self._ensure_profile_tokens()
        if not user_token:
            return {"error": "Could not access FatSecret diary. Check your Consumer Key/Secret."}

        if date_int is None:
            date_int = int(time.time() // 86400)

        data = await self._call(
            "food_entries.get",
            {"date": str(date_int)},
            user_token=user_token,
            user_secret=user_secret,
        )
        if "error" in data:
            return data

        try:
            entries_raw = data.get("food_entries", {}).get("food_entry", [])
            if isinstance(entries_raw, dict):
                entries_raw = [entries_raw]
            entries = []
            total_calories = 0.0
            for e in entries_raw:
                cal = float(e.get("calories", 0) or 0)
                total_calories += cal
                entries.append({
                    "entry_id": e.get("food_entry_id", ""),
                    "food_name": e.get("food_entry_name", ""),
                    "meal": e.get("meal", ""),
                    "servings": e.get("number_of_units", "1"),
                    "serving_description": e.get("serving_description", ""),
                    "calories": cal,
                    "carbs": str(e.get("carbohydrate", "0")) + "g",
                    "protein": str(e.get("protein", "0")) + "g",
                    "fat": str(e.get("fat", "0")) + "g",
                })
            return {"date": date_int, "total_calories": round(total_calories), "entries": entries}
        except Exception as ex:
            logger.exception("Error parsing food entries")
            return {"error": f"Error parsing food entries: {str(ex)}"}

    async def delete_food_entry(self, food_entry_id: str) -> Any:
        if not await self._is_configured():
            return {"error": "FatSecret not connected."}
        user_token, user_secret = await self._ensure_profile_tokens()
        if not user_token:
            return {"error": "Could not access FatSecret diary."}
        data = await self._call(
            "food_entry.delete",
            {"food_entry_id": food_entry_id},
            user_token=user_token,
            user_secret=user_secret,
        )
        if "error" in data:
            return data
        return {"ok": True, "message": f"Entry {food_entry_id} removed from diary"}
