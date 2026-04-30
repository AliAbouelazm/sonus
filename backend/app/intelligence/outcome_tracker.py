"""
Tracks outcomes of interventions and pattern actions.
Measures whether interventions actually helped.
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..memory.models import Outcome, Intervention
from ..memory.database import get_db

class OutcomeTracker:
    def __init__(self, app_state):
        self.app_state = app_state

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def schedule_check(
        self,
        action_taken: dict,
        metric_before: dict,
        check_delay_minutes: int = 10,
        intervention_id: int = None,
        pattern_id: int = None,
    ) -> Optional[int]:
        """Schedule an outcome check for later."""
        if not self._is_active_mode():
            return None

        check_at = datetime.utcnow() + timedelta(minutes=check_delay_minutes)
        async with get_db() as db:
            outcome = Outcome(
                intervention_id=intervention_id,
                pattern_id=pattern_id,
                triggered_at=datetime.utcnow(),
                check_at=check_at,
                metric_before=metric_before,
                action_taken=action_taken,
            )
            db.add(outcome)
            await db.commit()
            await db.refresh(outcome)
            return outcome.id

    async def record_result(self, outcome_id: int, metric_after: dict):
        """Record the measured outcome and calculate effectiveness."""
        async with get_db() as db:
            result = await db.execute(select(Outcome).where(Outcome.id == outcome_id))
            outcome = result.scalar_one_or_none()
            if not outcome:
                return

            outcome.metric_after = metric_after
            outcome.checked = True

            # Calculate improvement (lower stress/HR = better)
            before_stress = (outcome.metric_before or {}).get("stress_level", 0)
            after_stress = metric_after.get("stress_level", before_stress)

            if before_stress > 0:
                improvement = (before_stress - after_stress) / before_stress
                outcome.improvement = improvement
                outcome.was_effective = improvement > 0.05  # 5% improvement threshold

            await db.commit()

            # Update intervention effectiveness if linked
            if outcome.intervention_id:
                await self._update_intervention_effectiveness(db, outcome)

    async def _update_intervention_effectiveness(self, db: AsyncSession, outcome: Outcome):
        result = await db.execute(
            select(Intervention).where(Intervention.id == outcome.intervention_id)
        )
        intervention = result.scalar_one_or_none()
        if not intervention:
            return

        # Running average of effectiveness
        n = intervention.sample_count
        current_eff = intervention.effectiveness
        new_sample = 1.0 if outcome.was_effective else 0.0

        intervention.effectiveness = (current_eff * n + new_sample) / (n + 1)
        intervention.sample_count = n + 1
        await db.commit()

    async def get_pending_checks(self) -> list:
        """Get outcome checks that are due."""
        now = datetime.utcnow()
        async with get_db() as db:
            result = await db.execute(
                select(Outcome).where(
                    Outcome.checked == False,
                    Outcome.check_at <= now,
                )
            )
            return result.scalars().all()
