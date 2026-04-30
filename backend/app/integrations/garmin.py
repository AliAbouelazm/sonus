"""
Garmin Connect integration for biometric data.
Fetches heart rate, stress, body battery, HRV, and sleep data.
"""
import logging
import asyncio
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

class GarminIntegration:
    def __init__(self, config: dict):
        self.email = config.get("email") or config.get("username")
        self.password = config.get("password")
        self._client = None

    async def _get_client(self):
        """Lazy-initialize Garmin client."""
        if self._client is not None:
            return self._client

        try:
            import garminconnect
            client = garminconnect.Garmin(self.email, self.password)
            await asyncio.get_event_loop().run_in_executor(None, client.login)
            self._client = client
            return client
        except ImportError:
            raise RuntimeError("garminconnect package not installed. Run: pip install garminconnect")
        except Exception as e:
            raise RuntimeError(f"Garmin login failed: {e}")

    async def get_current_stats(self) -> Optional[dict]:
        """Get today's biometric stats."""
        try:
            client = await self._get_client()
            today = date.today().isoformat()

            def fetch():
                stats = {}
                try:
                    data = client.get_stats(today)
                    stats["steps"] = data.get("totalSteps")
                    stats["body_battery"] = data.get("bodyBatteryHighestValue")
                    stats["stress_level"] = data.get("averageStressLevel")
                    stats["heart_rate"] = data.get("restingHeartRate") or data.get("averageHeartRate")
                except Exception as e:
                    logger.debug(f"Garmin stats fetch partial failure: {e}")

                try:
                    hrv_data = client.get_hrv_data(today)
                    if hrv_data and "hrvSummary" in hrv_data:
                        stats["hrv"] = hrv_data["hrvSummary"].get("lastNight")
                except Exception:
                    pass

                return stats

            stats = await asyncio.get_event_loop().run_in_executor(None, fetch)
            return stats if any(v is not None for v in stats.values()) else None

        except Exception as e:
            logger.debug(f"Garmin get_current_stats failed: {e}")
            return None

    async def get_sleep_data(self, target_date: str = None) -> Optional[dict]:
        """Get sleep data for a given date (default: last night)."""
        try:
            client = await self._get_client()
            if not target_date:
                from datetime import date, timedelta
                target_date = (date.today() - timedelta(days=1)).isoformat()

            def fetch():
                return client.get_sleep_data(target_date)

            data = await asyncio.get_event_loop().run_in_executor(None, fetch)
            if not data or "dailySleepDTO" not in data:
                return None

            dto = data["dailySleepDTO"]
            return {
                "date": target_date,
                "sleep_score": dto.get("sleepScores", {}).get("overall", {}).get("value"),
                "total_sleep_seconds": dto.get("sleepTimeSeconds"),
                "deep_sleep_seconds": dto.get("deepSleepSeconds"),
                "rem_sleep_seconds": dto.get("remSleepSeconds"),
                "light_sleep_seconds": dto.get("lightSleepSeconds"),
                "awake_seconds": dto.get("awakeSleepSeconds"),
            }
        except Exception as e:
            logger.debug(f"Garmin get_sleep_data failed: {e}")
            return None
