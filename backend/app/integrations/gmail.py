import base64
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GmailIntegration:
    """Gmail read-only access via the same OAuth credentials as Google Calendar."""

    def __init__(self, calendar_integration: Any) -> None:
        self._cal = calendar_integration
        self._service: Any = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        cal_service = self._cal._get_service()
        if cal_service is None:
            return None
        from googleapiclient.discovery import build
        self._service = build("gmail", "v1", credentials=self._cal._credentials)
        return self._service

    def _not_ready(self) -> dict[str, str]:
        if not self._cal._oauth_configured():
            return {"error": "Gmail not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."}
        return {"error": "Google not authenticated. Visit /api/gcal/login to connect."}

    async def get_unread_count(self) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            results = service.users().labels().get(userId="me", id="INBOX").execute()
            return {
                "unread": results.get("messagesUnread", 0),
                "total": results.get("messagesTotal", 0),
            }
        except Exception as e:
            logger.exception("Failed to get unread count")
            return {"error": str(e)}

    async def get_recent_emails(self, max_results: int = 5, unread_only: bool = False) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            query = "is:unread" if unread_only else ""
            results = service.users().messages().list(
                userId="me",
                maxResults=max_results,
                q=query,
                labelIds=["INBOX"],
            ).execute()

            messages = results.get("messages", [])
            emails = []
            for msg_ref in messages[:max_results]:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                emails.append({
                    "id": msg["id"],
                    "from": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                    "unread": "UNREAD" in msg.get("labelIds", []),
                })

            return emails
        except Exception as e:
            logger.exception("Failed to get recent emails")
            return {"error": str(e)}

    async def read_email(self, message_id: str) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            msg = service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

            body_text = ""
            payload = msg.get("payload", {})
            if payload.get("body", {}).get("data"):
                body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            else:
                for part in payload.get("parts", []):
                    if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                        body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                        break

            body_text = body_text[:2000]

            return {
                "id": msg["id"],
                "from": headers.get("From", "Unknown"),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", "(no subject)"),
                "date": headers.get("Date", ""),
                "body": body_text,
            }
        except Exception as e:
            logger.exception("Failed to read email")
            return {"error": str(e)}

    async def search_emails(self, query: str, max_results: int = 5) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            results = service.users().messages().list(
                userId="me",
                maxResults=max_results,
                q=query,
            ).execute()

            messages = results.get("messages", [])
            emails = []
            for msg_ref in messages[:max_results]:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                emails.append({
                    "id": msg["id"],
                    "from": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                })

            return emails
        except Exception as e:
            logger.exception("Failed to search emails")
            return {"error": str(e)}
