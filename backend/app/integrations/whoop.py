"""
Whoop integration — recovery, strain, HRV, and sleep data.
Uses the Whoop Developer API v1.
"""
import logging
from datetime import date, timedelta
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

WHOOP_API = "https://api.prod.whoop.com/developer/v1"


class WhoopIntegration:
    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or config.get("token")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def get_current_stats(self) -> Optional[dict]:
        """Get today's recovery, strain, and most recent sleep."""
        if not self.api_key:
            return None

        stats = {}
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        async with httpx.AsyncClient(timeout=10, headers=self._headers()) as client:
            # Recovery (readiness score + HRV)
            try:
                r = await client.get(f"{WHOOP_API}/recovery", params={"start": yesterday, "end": today})
                if r.is_success:
                    records = r.json().get("records", [])
                    if records:
                        rec = records[-1]
                        score = rec.get("score", {})
                        stats["recovery_score"]  = score.get("recovery_score")   # 0-100
                        stats["hrv"]             = score.get("hrv_rmssd_milli")
                        stats["resting_hr"]      = score.get("resting_heart_rate")
                        # Map recovery score → stress proxy (inverted)
                        if stats.get("recovery_score") is not None:
                            stats["stress_level"] = 100 - stats["recovery_score"]
                        if stats.get("resting_hr"):
                            stats["heart_rate"] = stats["resting_hr"]
            except Exception as e:
                logger.debug(f"Whoop recovery fetch failed: {e}")

            # Strain (activity load)
            try:
                r = await client.get(f"{WHOOP_API}/cycle", params={"start": yesterday, "end": today})
                if r.is_success:
                    records = r.json().get("records", [])
                    if records:
                        cycle = records[-1].get("score", {})
                        stats["strain"]       = cycle.get("strain")          # 0-21
                        stats["avg_heart_rate"] = cycle.get("average_heart_rate")
                        stats["body_battery"] = max(0, 100 - (cycle.get("strain", 0) / 21 * 100)) if cycle.get("strain") else None
            except Exception as e:
                logger.debug(f"Whoop cycle fetch failed: {e}")

            # Sleep
            try:
                r = await client.get(f"{WHOOP_API}/activity/sleep", params={"start": yesterday, "end": today})
                if r.is_success:
                    records = r.json().get("records", [])
                    if records:
                        sleep = records[-1].get("score", {})
                        stats["sleep_score"]        = sleep.get("sleep_performance_percentage")
                        stats["sleep_efficiency"]   = sleep.get("sleep_efficiency_percentage")
                        stats["respiratory_rate"]   = sleep.get("respiratory_rate")
            except Exception as e:
                logger.debug(f"Whoop sleep fetch failed: {e}")

        return stats if any(v is not None for v in stats.values()) else None
