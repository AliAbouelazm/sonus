import json
import logging
import os
from datetime import datetime, timedelta, timezone, date as date_type, time as time_type
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from icalendar import Calendar
import recurring_ical_events

from backend.app.config import settings
from backend.app.integrations.config_helper import get_integration_config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.readonly",
]
LOCAL_TZ = "America/Chicago"

TOKEN_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".gcal_token.json"
)


class GoogleCalendarIntegration:
    """Google Calendar with ICS for reading and OAuth for writing.

    Reading always uses the ICS feed (fast, no auth needed).
    Writing (create/update/delete events) uses OAuth if configured.
    """

    def __init__(self) -> None:
        self._cached_cal: Calendar | None = None
        self._cache_time: float = 0
        self._credentials: Any = None
        self._service: Any = None
        self._pending_flow: Any = None
        # Override credentials set from the UI (takes priority over .env)
        self._ui_client_id: str = ""
        self._ui_client_secret: str = ""

    def set_oauth_credentials(self, client_id: str, client_secret: str) -> None:
        """Override the OAuth credentials with values entered in the Sonus UI."""
        self._ui_client_id = client_id or ""
        self._ui_client_secret = client_secret or ""
        # Reset cached auth manager so next login uses new credentials
        self._pending_flow = None

    def _get_client_id(self) -> str:
        return self._ui_client_id or ""

    def _get_client_secret(self) -> str:
        return self._ui_client_secret or ""

    # ── OAuth helpers ──

    def _oauth_configured(self) -> bool:
        return bool(self._get_client_id() and self._get_client_secret())

    def _get_flow(self) -> Any:
        from google_auth_oauthlib.flow import Flow

        client_config = {
            "web": {
                "client_id": self._get_client_id(),
                "client_secret": self._get_client_secret(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=SCOPES)
        flow.redirect_uri = settings.google_redirect_uri
        return flow

    def get_auth_url(self) -> str:
        if not self._oauth_configured():
            return ""
        self._pending_flow = self._get_flow()
        url, _ = self._pending_flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return url

    def handle_callback(self, code: str) -> bool:
        try:
            flow = self._pending_flow if self._pending_flow else self._get_flow()
            flow.fetch_token(code=code)
            self._pending_flow = None
            creds = flow.credentials
            token_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or []),
            }
            with open(TOKEN_CACHE, "w") as f:
                json.dump(token_data, f)
            self._credentials = creds
            self._service = None
            logger.info("Google Calendar OAuth authenticated successfully")
            return True
        except Exception as e:
            logger.error("Google Calendar OAuth callback failed: %s", e)
            return False

    def is_authenticated(self) -> bool:
        if self._credentials is not None:
            return True
        return os.path.exists(TOKEN_CACHE)

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        from google.auth.transport.requests import Request as GRequest
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = self._credentials
        if creds is None and os.path.exists(TOKEN_CACHE):
            with open(TOKEN_CACHE) as f:
                token_data = json.load(f)
            creds = Credentials(
                token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id", settings.google_client_id),
                client_secret=token_data.get("client_secret", settings.google_client_secret),
                scopes=token_data.get("scopes"),
            )

        if creds is None:
            return None

        try:
            if creds.expired and creds.refresh_token:
                logger.info("Google Calendar token expired, refreshing...")
                creds.refresh(GRequest())
                token_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes or []),
                }
                with open(TOKEN_CACHE, "w") as f:
                    json.dump(token_data, f)
                logger.info("Google Calendar token refreshed successfully")
        except Exception as e:
            logger.error("Failed to refresh Google Calendar token: %s", e)
            return None

        self._credentials = creds
        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    # ── Read (ICS — always available) ──

    async def _get_events_via_api(self, days_ahead: int = 1) -> Any:
        """Read events via Google Calendar API (OAuth). Used when no ICS URL is configured."""
        import asyncio
        try:
            service = self._get_service()
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            def fetch():
                result = service.events().list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=50,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
                return result.get("items", [])

            items = await asyncio.get_event_loop().run_in_executor(None, fetch)

            events = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                start_str = start.get("dateTime") or start.get("date", "")
                end_str = end.get("dateTime") or end.get("date", "")
                events.append({
                    "title": item.get("summary", "Untitled"),
                    "start": start_str,
                    "end": end_str,
                    "location": (item.get("location") or "")[:200],
                })
            return events
        except Exception as e:
            logger.error("Failed to fetch events via Google Calendar API: %s", e)
            return {"error": f"Could not fetch Google Calendar: {str(e)}"}

    async def get_events(self, days_ahead: int = 1) -> Any:
        db_config = await get_integration_config("google_calendar")
        url = (db_config or {}).get("ics_url") or settings.google_calendar_ics_url

        # No ICS URL — fall back to OAuth API if authenticated
        if not url:
            if self.is_authenticated():
                return await self._get_events_via_api(days_ahead)
            return {"error": "Google Calendar not connected. Add it on the Integrations page."}

        try:
            now = datetime.now(timezone.utc)
            cache_age = now.timestamp() - self._cache_time

            if self._cached_cal is None or cache_age > 300:
                # Retry up to 3 times on transient SSL/network errors
                import asyncio
                last_err = None
                for attempt in range(3):
                    try:
                        async with httpx.AsyncClient(timeout=15.0) as client:
                            response = await client.get(url)
                            response.raise_for_status()
                        self._cached_cal = Calendar.from_ical(response.text)
                        self._cache_time = now.timestamp()
                        last_err = None
                        break
                    except Exception as fetch_err:
                        last_err = fetch_err
                        if attempt < 2:
                            await asyncio.sleep(1.5 ** attempt)

                if last_err is not None:
                    if self._cached_cal is not None:
                        logger.warning("Using stale calendar cache after fetch error: %s", last_err)
                    else:
                        raise last_err

            start_window = now - timedelta(hours=12)
            end_window = now + timedelta(days=days_ahead)
            expanded = recurring_ical_events.of(self._cached_cal).between(
                start_window, end_window
            )

            events = []
            for component in expanded:
                summary = str(component.get("summary", "Untitled"))
                location = str(component.get("location", "")) if component.get("location") else ""

                dtstart = component.get("dtstart")
                dtend = component.get("dtend")
                start_dt = self._normalize_dt(dtstart.dt if dtstart else None)
                end_dt = self._normalize_dt(dtend.dt if dtend else None)

                events.append({
                    "title": summary,
                    "start": start_dt.isoformat() if start_dt else "",
                    "end": end_dt.isoformat() if end_dt else "",
                    "location": location[:200],
                })

            events.sort(key=lambda e: e.get("start", ""))
            return events

        except httpx.HTTPError as e:
            logger.error("Failed to fetch Google Calendar ICS: %s", e)
            return {"error": f"Could not fetch Google Calendar: {str(e)}"}
        except Exception as e:
            logger.exception("Error parsing Google Calendar ICS")
            return {"error": f"Error parsing Google Calendar: {str(e)}"}

    # ── Write (OAuth — requires setup) ──

    def _write_not_ready(self) -> dict[str, str] | None:
        if not self._oauth_configured():
            return {"error": "Google Calendar write access not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."}
        if not self.is_authenticated():
            return {"error": "Google Calendar not authenticated. Visit /api/gcal/login to connect your account."}
        return None

    async def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
    ) -> Any:
        guard = self._write_not_ready()
        if guard is not None:
            return guard
        service = self._get_service()
        if service is None:
            return {"error": "Failed to connect to Google Calendar API. Try re-authenticating at /api/gcal/login."}

        try:
            is_all_day = len(start) <= 10

            if is_all_day:
                event_body: dict[str, Any] = {
                    "summary": title,
                    "start": {"date": start},
                    "end": {"date": end or start},
                }
            else:
                event_body = {
                    "summary": title,
                    "start": {"dateTime": start, "timeZone": LOCAL_TZ},
                    "end": {"dateTime": end, "timeZone": LOCAL_TZ},
                }

            if description:
                event_body["description"] = description
            if location:
                event_body["location"] = location

            created = service.events().insert(calendarId="primary", body=event_body).execute()

            self._cached_cal = None

            return {
                "status": "created",
                "event_id": created.get("id", ""),
                "title": created.get("summary", ""),
                "link": created.get("htmlLink", ""),
            }
        except Exception as e:
            logger.exception("Failed to create Google Calendar event")
            return {"error": f"Failed to create event: {str(e)}"}

    async def delete_event(self, event_id: str) -> Any:
        guard = self._write_not_ready()
        if guard is not None:
            return guard
        service = self._get_service()
        if service is None:
            return {"error": "Failed to connect to Google Calendar API. Try re-authenticating at /api/gcal/login."}

        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            self._cached_cal = None
            return {"status": "deleted", "event_id": event_id}
        except Exception as e:
            logger.exception("Failed to delete Google Calendar event")
            return {"error": f"Failed to delete event: {str(e)}"}

    async def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Any:
        guard = self._write_not_ready()
        if guard is not None:
            return guard
        service = self._get_service()
        if service is None:
            return {"error": "Failed to connect to Google Calendar API. Try re-authenticating at /api/gcal/login."}

        try:
            existing = service.events().get(calendarId="primary", eventId=event_id).execute()

            if title:
                existing["summary"] = title
            if description is not None:
                existing["description"] = description
            if location is not None:
                existing["location"] = location
            if start:
                if len(start) <= 10:
                    existing["start"] = {"date": start}
                else:
                    existing["start"] = {"dateTime": start, "timeZone": LOCAL_TZ}
            if end:
                if len(end) <= 10:
                    existing["end"] = {"date": end}
                else:
                    existing["end"] = {"dateTime": end, "timeZone": LOCAL_TZ}

            updated = service.events().update(
                calendarId="primary", eventId=event_id, body=existing
            ).execute()

            self._cached_cal = None

            return {
                "status": "updated",
                "event_id": updated.get("id", ""),
                "title": updated.get("summary", ""),
                "link": updated.get("htmlLink", ""),
            }
        except Exception as e:
            logger.exception("Failed to update Google Calendar event")
            return {"error": f"Failed to update event: {str(e)}"}

    async def search_events(self, query: str, days_ahead: int = 30) -> Any:
        """Search for events by keyword using the API (for getting event IDs for updates/deletes)."""
        guard = self._write_not_ready()
        if guard is not None:
            return guard
        service = self._get_service()
        if service is None:
            return {"error": "Failed to connect to Google Calendar API. Try re-authenticating at /api/gcal/login."}

        try:
            now = datetime.now(timezone.utc).isoformat()
            future = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

            results = service.events().list(
                calendarId="primary",
                q=query,
                timeMin=now,
                timeMax=future,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = []
            for item in results.get("items", []):
                start = item.get("start", {})
                end = item.get("end", {})
                events.append({
                    "event_id": item["id"],
                    "title": item.get("summary", "Untitled"),
                    "start": start.get("dateTime") or start.get("date", ""),
                    "end": end.get("dateTime") or end.get("date", ""),
                    "location": item.get("location", ""),
                })
            return events
        except Exception as e:
            logger.exception("Failed to search Google Calendar events")
            return {"error": f"Failed to search events: {str(e)}"}

    @staticmethod
    def _normalize_dt(dt: Any) -> Any:
        if dt is None:
            return None
        if isinstance(dt, date_type) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, time_type.min, tzinfo=timezone.utc)
        elif isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
