import logging
import time
from typing import Any

import httpx

from backend.app.config import settings
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)


class WeatherIntegration:
    """OpenWeatherMap API integration for current conditions and forecast."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 600  # 10 minutes

    async def get_current(self) -> Any:
        db_config = await get_integration_config("weather")
        api_key = (db_config or {}).get("api_key") or settings.weather_api_key
        city = (db_config or {}).get("city") or settings.weather_city

        if not api_key:
            return {"error": "Weather not connected. Add it on the Integrations page."}

        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        import asyncio
        last_err = None
        current = forecast = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    current_resp = await client.get(
                        f"{self.BASE_URL}/weather",
                        params={"q": city, "appid": api_key, "units": "imperial"},
                    )
                    current_resp.raise_for_status()
                    current = current_resp.json()

                    forecast_resp = await client.get(
                        f"{self.BASE_URL}/forecast",
                        params={"q": city, "appid": api_key, "units": "imperial", "cnt": 8},
                    )
                    forecast_resp.raise_for_status()
                    forecast = forecast_resp.json()
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(1.5 ** attempt)

        if last_err is not None:
            if self._cache:
                logger.warning("Using stale weather cache after fetch error: %s", last_err)
                return self._cache
            logger.error("Weather fetch failed after retries: %s", last_err)
            return {"error": f"Could not fetch weather: {str(last_err)}"}

        try:
            weather_desc = current["weather"][0]["description"] if current.get("weather") else "unknown"
            forecast_items = []
            for item in forecast.get("list", [])[:5]:
                forecast_items.append({
                    "time": item.get("dt_txt", ""),
                    "temp": item["main"]["temp"],
                    "description": item["weather"][0]["description"] if item.get("weather") else "",
                })

            result = {
                "city": city,
                "temp": current["main"]["temp"],
                "feels_like": current["main"]["feels_like"],
                "humidity": current["main"]["humidity"],
                "description": weather_desc,
                "wind_speed": current.get("wind", {}).get("speed", 0),
                "forecast": forecast_items,
            }

            self._cache = result
            self._cache_time = now
            return result

        except Exception as e:
            logger.exception("Weather integration error")
            return {"error": f"Weather error: {str(e)}"}
