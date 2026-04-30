"""
Confidence scoring system for learned patterns.
Adjustments based on user feedback signals.
"""
from datetime import datetime, timedelta
from sqlalchemy import select, update
from ..memory.models import Pattern, PatternDenial
from ..memory.database import get_db

# Confidence adjustment constants
ADJUST = {
    "approve":         +0.08,
    "always":          +0.25,
    "passive_approve": +0.02,
    "user_did_it":     +0.05,
    "no":              -0.12,
    "not_now":         -0.03,
    "undo_fast":       -0.25,   # within 2 min
    "undo_slow":       -0.15,   # after 2 min
    "never":           -0.40,
    "did_opposite":    -0.10,
}

WEEKLY_DECAY = 0.01   # lose 1% per week if not reinforced

class ConfidenceSystem:
    def __init__(self, app_state):
        self.app_state = app_state

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def adjust(self, pattern_id: int, signal: str, context: dict = None):
        """Apply a confidence adjustment to a pattern."""
        if not self._is_active_mode():
            return

        delta = ADJUST.get(signal, 0)
        if delta == 0:
            return

        async with get_db() as db:
            result = await db.execute(select(Pattern).where(Pattern.id == pattern_id))
            pattern = result.scalar_one_or_none()
            if not pattern:
                return

            new_conf = max(0.0, min(1.0, pattern.confidence + delta))
            pattern.confidence = new_conf
            pattern.last_reinforced = datetime.utcnow()

            # Record denial context
            if signal in ("no", "not_now", "never", "undo_fast", "undo_slow"):
                denial = PatternDenial(
                    pattern_id=pattern_id,
                    denial_type=signal,
                    context_snapshot=context or {},
                )
                db.add(denial)

            await db.commit()

    async def apply_decay(self):
        """Apply weekly decay to patterns not recently reinforced. Only in active mode."""
        if not self._is_active_mode():
            return

        cutoff = datetime.utcnow() - timedelta(weeks=1)
        async with get_db() as db:
            result = await db.execute(
                select(Pattern).where(
                    Pattern.is_active == True,
                    Pattern.last_reinforced < cutoff,
                )
            )
            patterns = result.scalars().all()
            for p in patterns:
                p.confidence = max(0.0, p.confidence - WEEKLY_DECAY)
            await db.commit()

    async def check_denial_match(self, pattern_id: int, current_context: dict) -> bool:
        """
        Check if the current context is similar to past denial contexts for this pattern.
        Returns True if we should suppress the pattern suggestion.
        """
        async with get_db() as db:
            result = await db.execute(
                select(PatternDenial).where(
                    PatternDenial.pattern_id == pattern_id,
                    PatternDenial.denial_type.in_(["no", "never", "undo_fast"]),
                ).order_by(PatternDenial.denied_at.desc()).limit(10)
            )
            denials = result.scalars().all()

        if not denials:
            return False

        # Simple context matching: compare hour of day and day type
        current_hour = current_context.get("hour", -1)
        current_is_weekend = current_context.get("is_weekend", False)

        for denial in denials:
            ctx = denial.context_snapshot or {}
            denied_hour = ctx.get("hour", -1)
            denied_weekend = ctx.get("is_weekend", False)

            # If same time period and same day type, suppress
            if abs(current_hour - denied_hour) <= 1 and current_is_weekend == denied_weekend:
                return True

        return False

    async def get_pattern(self, pattern_id: int) -> dict:
        async with get_db() as db:
            result = await db.execute(select(Pattern).where(Pattern.id == pattern_id))
            p = result.scalar_one_or_none()
            if not p:
                return None
            return {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "conditions": p.conditions,
                "actions": p.actions,
                "confidence": p.confidence,
                "trigger_count": p.trigger_count,
                "last_triggered": p.last_triggered.isoformat() if p.last_triggered else None,
            }

    async def list_patterns(self, active_only: bool = True) -> list:
        async with get_db() as db:
            q = select(Pattern)
            if active_only:
                q = q.where(Pattern.is_active == True)
            q = q.order_by(Pattern.confidence.desc())
            result = await db.execute(q)
            patterns = result.scalars().all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "confidence": p.confidence,
                    "conditions": p.conditions,
                    "actions": p.actions,
                    "trigger_count": p.trigger_count,
                    "source": p.source,
                    "is_active": p.is_active,
                }
                for p in patterns
            ]

    async def create_pattern(self, name: str, description: str, conditions: list, actions: list,
                              confidence: float = 0.3, source: str = "discovered") -> int:
        async with get_db() as db:
            p = Pattern(
                name=name,
                description=description,
                conditions=conditions,
                actions=actions,
                confidence=confidence,
                source=source,
            )
            db.add(p)
            await db.commit()
            await db.refresh(p)
            return p.id
