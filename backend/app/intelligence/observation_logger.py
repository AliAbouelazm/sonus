"""
Logs observations about device changes, user actions, biometrics, etc.
Only logs when in TRAIN mode.
"""
import json
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..memory.models import Observation
from ..memory.database import get_db

class ObservationLogger:
    def __init__(self, app_state):
        self.app_state = app_state

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def log(
        self,
        obs_type: str,
        subject: Optional[str] = None,
        old_value: Any = None,
        new_value: Any = None,
        triggered_by: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> Optional[int]:
        """Log an observation. Returns observation id or None if not in active mode."""
        if not self._is_active_mode():
            return None

        async with get_db() as db:
            obs = Observation(
                obs_type=obs_type,
                subject=subject,
                old_value=old_value,
                new_value=new_value,
                triggered_by=triggered_by,
                context=context or {},
            )
            db.add(obs)
            await db.commit()
            await db.refresh(obs)
            return obs.id

    async def get_recent(self, obs_type: Optional[str] = None, limit: int = 50) -> list:
        async with get_db() as db:
            q = select(Observation).order_by(Observation.timestamp.desc()).limit(limit)
            if obs_type:
                q = q.where(Observation.obs_type == obs_type)
            result = await db.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat(),
                    "type": r.obs_type,
                    "subject": r.subject,
                    "old_value": r.old_value,
                    "new_value": r.new_value,
                    "triggered_by": r.triggered_by,
                    "context": r.context,
                }
                for r in rows
            ]

    async def count_pattern_occurrences(self, obs_type: str, subject: str, context_hour_range: tuple = None) -> int:
        """Count how many times a specific observation has occurred, optionally filtered by hour range."""
        async with get_db() as db:
            q = select(func.count(Observation.id)).where(
                Observation.obs_type == obs_type,
                Observation.subject == subject,
            )
            result = await db.execute(q)
            return result.scalar() or 0
