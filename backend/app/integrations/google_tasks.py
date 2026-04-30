import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GoogleTasksIntegration:
    """Google Tasks via the same OAuth credentials as Google Calendar."""

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
        self._service = build("tasks", "v1", credentials=self._cal._credentials)
        return self._service

    def _not_ready(self) -> dict[str, str]:
        if not self._cal._oauth_configured():
            return {"error": "Google Tasks not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."}
        return {"error": "Google not authenticated. Visit /api/gcal/login to connect."}

    async def list_task_lists(self) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            results = service.tasklists().list(maxResults=10).execute()
            return [
                {"id": tl["id"], "title": tl.get("title", "Untitled")}
                for tl in results.get("items", [])
            ]
        except Exception as e:
            logger.exception("Failed to list task lists")
            return {"error": str(e)}

    async def get_tasks(self, task_list_id: Optional[str] = None, show_completed: bool = False) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            if not task_list_id:
                lists = await self.list_task_lists()
                if isinstance(lists, dict) and "error" in lists:
                    return lists
                if not lists:
                    return {"error": "No task lists found."}
                task_list_id = lists[0]["id"]

            results = service.tasks().list(
                tasklist=task_list_id,
                showCompleted=show_completed,
                showHidden=False,
                maxResults=20,
            ).execute()

            tasks = []
            for t in results.get("items", []):
                tasks.append({
                    "id": t["id"],
                    "title": t.get("title", ""),
                    "notes": t.get("notes", ""),
                    "due": t.get("due", ""),
                    "status": t.get("status", ""),
                    "completed": t.get("completed", ""),
                })
            return tasks
        except Exception as e:
            logger.exception("Failed to get tasks")
            return {"error": str(e)}

    async def create_task(
        self,
        title: str,
        notes: str = "",
        due: str = "",
        task_list_id: Optional[str] = None,
    ) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            if not task_list_id:
                lists = await self.list_task_lists()
                if isinstance(lists, dict) and "error" in lists:
                    return lists
                if not lists:
                    return {"error": "No task lists found."}
                task_list_id = lists[0]["id"]

            body: dict[str, Any] = {"title": title}
            if notes:
                body["notes"] = notes
            if due:
                if len(due) <= 10:
                    due += "T00:00:00.000Z"
                body["due"] = due

            result = service.tasks().insert(tasklist=task_list_id, body=body).execute()
            return {
                "status": "created",
                "id": result.get("id", ""),
                "title": result.get("title", ""),
            }
        except Exception as e:
            logger.exception("Failed to create task")
            return {"error": str(e)}

    async def complete_task(self, task_id: str, task_list_id: Optional[str] = None) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            if not task_list_id:
                lists = await self.list_task_lists()
                if isinstance(lists, dict) and "error" in lists:
                    return lists
                if not lists:
                    return {"error": "No task lists found."}
                task_list_id = lists[0]["id"]

            task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
            task["status"] = "completed"
            result = service.tasks().update(
                tasklist=task_list_id, task=task_id, body=task
            ).execute()
            return {"status": "completed", "title": result.get("title", "")}
        except Exception as e:
            logger.exception("Failed to complete task")
            return {"error": str(e)}

    async def delete_task(self, task_id: str, task_list_id: Optional[str] = None) -> Any:
        service = self._get_service()
        if service is None:
            return self._not_ready()
        try:
            if not task_list_id:
                lists = await self.list_task_lists()
                if isinstance(lists, dict) and "error" in lists:
                    return lists
                if not lists:
                    return {"error": "No task lists found."}
                task_list_id = lists[0]["id"]

            service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
            return {"status": "deleted", "task_id": task_id}
        except Exception as e:
            logger.exception("Failed to delete task")
            return {"error": str(e)}
