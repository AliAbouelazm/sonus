import json
import logging
from datetime import datetime
from typing import Any, Optional

import dateparser
from sqlalchemy import select, update

from backend.app.memory.database import async_session
from backend.app.memory.models import Conversation, DeviceStateRecord, IntegrationConfig, Memory, Reminder

logger = logging.getLogger(__name__)


class MemoryStore:
    """All CRUD operations for the persistent memory system."""

    async def store_memory(
        self,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        context: Optional[dict] = None,
    ) -> dict[str, Any]:
        async with async_session() as session:
            mem = Memory(
                memory_type=memory_type,
                content=content,
                importance=importance,
                context=context,
            )
            session.add(mem)
            await session.commit()
            logger.info("Stored memory: [%s] %s", memory_type, content[:80])
            return {"id": mem.id, "content": content}

    async def recall_memories(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        async with async_session() as session:
            stmt = select(Memory).where(Memory.is_active == True)  # noqa: E712
            if memory_type:
                stmt = stmt.where(Memory.memory_type == memory_type)
            stmt = stmt.order_by(Memory.importance.desc(), Memory.created_at.desc())
            result = await session.execute(stmt)
            all_memories = result.scalars().all()

        keywords = set(query.lower().split())
        scored: list[tuple[float, Memory]] = []
        for mem in all_memories:
            content_lower = mem.content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > 0 or not keywords:
                score = matches * 0.5 + mem.importance
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": m.id,
                "type": m.memory_type,
                "content": m.content,
                "importance": m.importance,
                "created_at": m.created_at.isoformat(),
            }
            for _, m in scored[:limit]
        ]

    async def create_reminder(
        self,
        title: str,
        when: str,
        description: str = "",
    ) -> dict[str, Any]:
        parsed = dateparser.parse(
            when,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(),
            },
        )
        if parsed is None:
            return {"error": f"Could not parse time expression: '{when}'"}

        async with async_session() as session:
            reminder = Reminder(
                title=title,
                description=description,
                remind_at=parsed,
            )
            session.add(reminder)
            await session.commit()
            logger.info("Created reminder: %s at %s", title, parsed)
            return {
                "id": reminder.id,
                "title": title,
                "remind_at": parsed.isoformat(),
                "description": description,
            }

    async def get_reminders(self, include_completed: bool = False) -> list[dict[str, Any]]:
        async with async_session() as session:
            stmt = select(Reminder).order_by(Reminder.remind_at)
            if not include_completed:
                stmt = stmt.where(Reminder.is_completed == False)  # noqa: E712
            result = await session.execute(stmt)
            reminders = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "description": r.description or "",
                    "remind_at": r.remind_at.isoformat(),
                    "is_completed": r.is_completed,
                }
                for r in reminders
            ]

    async def get_due_reminders(self) -> list[dict[str, Any]]:
        now = datetime.utcnow()
        async with async_session() as session:
            stmt = (
                select(Reminder)
                .where(Reminder.is_completed == False)  # noqa: E712
                .where(Reminder.remind_at <= now)
            )
            result = await session.execute(stmt)
            due = result.scalars().all()

            reminders = []
            for r in due:
                r.is_completed = True
                reminders.append({
                    "id": r.id,
                    "title": r.title,
                    "description": r.description or "",
                    "remind_at": r.remind_at.isoformat(),
                })
            await session.commit()
            return reminders

    async def save_device_states(self, states: dict[str, dict[str, Any]], device_types: dict[str, str]) -> None:
        async with async_session() as session:
            for device_id, state in states.items():
                existing = await session.execute(
                    select(DeviceStateRecord).where(DeviceStateRecord.device_id == device_id)
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.state = state
                    record.updated_at = datetime.utcnow()
                else:
                    record = DeviceStateRecord(
                        device_id=device_id,
                        device_type=device_types.get(device_id, "unknown"),
                        state=state,
                    )
                    session.add(record)
            await session.commit()

    async def load_device_states(self) -> dict[str, dict[str, Any]]:
        async with async_session() as session:
            result = await session.execute(select(DeviceStateRecord))
            records = result.scalars().all()
            return {r.device_id: r.state for r in records}

    async def save_conversation(self, role: str, content: str, session_id: str = "default") -> None:
        async with async_session() as session:
            conv = Conversation(role=role, content=content, session_id=session_id)
            session.add(conv)
            await session.commit()

    async def get_integration_configs(self) -> list[dict[str, Any]]:
        async with async_session() as session:
            result = await session.execute(select(IntegrationConfig).where(IntegrationConfig.is_connected == True))  # noqa: E712
            configs = result.scalars().all()
            return [self._integration_to_dict(c) for c in configs]

    async def save_integration_config(
        self,
        integration_id: str,
        instance_id: str,
        config: dict,
        display_name: str = "",
    ) -> dict[str, Any]:
        async with async_session() as session:
            existing = await session.execute(
                select(IntegrationConfig).where(IntegrationConfig.instance_id == instance_id)
            )
            record = existing.scalar_one_or_none()
            if record:
                record.config = config
                record.display_name = display_name or record.display_name
                record.is_connected = True
                record.last_status = "connected"
            else:
                record = IntegrationConfig(
                    integration_id=integration_id,
                    instance_id=instance_id,
                    display_name=display_name or integration_id,
                    config=config,
                    is_connected=True,
                    last_status="connected",
                )
                session.add(record)
            await session.commit()
            await session.refresh(record)
            return self._integration_to_dict(record)

    async def delete_integration_config(self, instance_id: str) -> bool:
        async with async_session() as session:
            existing = await session.execute(
                select(IntegrationConfig).where(IntegrationConfig.instance_id == instance_id)
            )
            record = existing.scalar_one_or_none()
            if record:
                await session.delete(record)
                await session.commit()
                return True
            return False

    def _integration_to_dict(self, c: IntegrationConfig) -> dict[str, Any]:
        return {
            "id": c.id,
            "integration_id": c.integration_id,
            "instance_id": c.instance_id,
            "display_name": c.display_name,
            "config": c.config,
            "is_connected": c.is_connected,
            "connected_at": c.connected_at.isoformat() if c.connected_at else None,
            "last_status": c.last_status,
        }

    async def get_conversation_history(
        self, session_id: str = "default", limit: int = 50
    ) -> list[dict[str, Any]]:
        async with async_session() as session:
            stmt = (
                select(Conversation)
                .where(Conversation.session_id == session_id)
                .order_by(Conversation.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            messages = result.scalars().all()
            messages.reverse()
            return [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
                for m in messages
            ]

    # ── Patterns ────────────────────────────────────────────────
    async def get_patterns(self, active_only: bool = True) -> list:
        async with async_session() as session:
            from .models import Pattern
            q = select(Pattern)
            if active_only:
                q = q.where(Pattern.is_active == True)  # noqa: E712
            q = q.order_by(Pattern.confidence.desc())
            result = await session.execute(q)
            patterns = result.scalars().all()
            return [
                {
                    "id": p.id, "name": p.name, "description": p.description,
                    "confidence": p.confidence, "conditions": p.conditions,
                    "actions": p.actions, "trigger_count": p.trigger_count,
                    "source": p.source, "is_active": p.is_active,
                }
                for p in patterns
            ]

    async def get_observations(self, obs_type: str = None, limit: int = 50) -> list:
        async with async_session() as session:
            from .models import Observation
            q = select(Observation).order_by(Observation.timestamp.desc()).limit(limit)
            if obs_type:
                q = q.where(Observation.obs_type == obs_type)
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id, "timestamp": r.timestamp.isoformat(),
                    "type": r.obs_type, "subject": r.subject,
                    "new_value": r.new_value, "triggered_by": r.triggered_by,
                }
                for r in rows
            ]
