import logging
from typing import Any, Callable, Coroutine, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.memory.store import MemoryStore

logger = logging.getLogger(__name__)

OnReminder = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class SonusScheduler:
    """APScheduler-based background task scheduler for reminders and routines."""

    def __init__(self, memory_store: MemoryStore) -> None:
        self.scheduler = AsyncIOScheduler()
        self.memory_store = memory_store
        self._on_reminder: Optional[OnReminder] = None

    def set_on_reminder(self, callback: OnReminder) -> None:
        self._on_reminder = callback

    def start(self) -> None:
        self.scheduler.add_job(
            self._check_reminders,
            "interval",
            seconds=60,
            id="reminder_checker",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started – checking reminders every 60s")

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def _check_reminders(self) -> None:
        try:
            due = await self.memory_store.get_due_reminders()
            for reminder in due:
                logger.info("Reminder due: %s", reminder["title"])
                if self._on_reminder:
                    await self._on_reminder(reminder)
        except Exception:
            logger.exception("Error checking reminders")
