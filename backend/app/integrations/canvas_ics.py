import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from icalendar import Calendar

from backend.app.config import settings
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)


class CanvasICSIntegration:
    """Fetches and parses a Canvas LMS ICS calendar feed for assignments and exams."""

    def __init__(self) -> None:
        self._cached_events: list[dict[str, Any]] = []
        self._cache_time: float = 0

    async def get_assignments(self, days_ahead: int = 7) -> Any:
        db_config = await get_integration_config("canvas")
        url = (db_config or {}).get("ics_url") or settings.canvas_ics_url
        if not url:
            return {"error": "Canvas not connected. Add it on the Integrations page."}

        try:
            now = datetime.now(timezone.utc)
            cache_age = (now.timestamp() - self._cache_time)
            if self._cached_events and cache_age < 300:
                return self._filter_events(self._cached_events, days_ahead)

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            cal = Calendar.from_ical(response.text)
            events = []

            for component in cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get("dtstart")
                    dtend = component.get("dtend")
                    summary = str(component.get("summary", "Untitled"))
                    description = str(component.get("description", "")) if component.get("description") else ""

                    start_dt = dtstart.dt if dtstart else None
                    if start_dt and not isinstance(start_dt, datetime):
                        start_dt = datetime.combine(start_dt, datetime.min.time(), tzinfo=timezone.utc)
                    elif start_dt and start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)

                    end_dt = None
                    if dtend:
                        end_dt = dtend.dt
                        if end_dt and not isinstance(end_dt, datetime):
                            end_dt = datetime.combine(end_dt, datetime.min.time(), tzinfo=timezone.utc)
                        elif end_dt and end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=timezone.utc)

                    events.append({
                        "title": summary,
                        "start": start_dt.isoformat() if start_dt else "",
                        "end": end_dt.isoformat() if end_dt else "",
                        "description": description[:200],
                    })

            self._cached_events = events
            self._cache_time = now.timestamp()
            return self._filter_events(events, days_ahead)

        except httpx.HTTPError as e:
            logger.error("Failed to fetch Canvas ICS: %s", e)
            return {"error": f"Could not fetch Canvas calendar: {str(e)}"}
        except Exception as e:
            logger.exception("Error parsing Canvas ICS")
            return {"error": f"Error parsing Canvas calendar: {str(e)}"}

    @staticmethod
    def _filter_events(events: list[dict[str, Any]], days_ahead: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        filtered = []
        for ev in events:
            start_str = ev.get("start", "")
            if not start_str:
                continue
            try:
                start = datetime.fromisoformat(start_str)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if now <= start <= cutoff:
                    filtered.append(ev)
            except ValueError:
                continue
        filtered.sort(key=lambda e: e.get("start", ""))
        return filtered
