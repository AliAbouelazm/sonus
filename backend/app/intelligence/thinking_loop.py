"""
Autonomous thinking loop — runs every 2-5 minutes in TRAIN mode only.
Uses LLM for complex reasoning, but checks patterns first without LLM.
"""
import logging
import asyncio
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from ..memory.models import Pattern
from ..memory.database import get_db
from .confidence import ConfidenceSystem
from .observation_logger import ObservationLogger

logger = logging.getLogger(__name__)

# Pattern matching thresholds
AUTO_EXECUTE_THRESHOLD = 0.85
SUGGEST_THRESHOLD = 0.50

class ThinkingLoop:
    def __init__(self, app_state, agent, device_manager, obs_logger: ObservationLogger, confidence: ConfidenceSystem, ws_manager=None):
        self.app_state = app_state
        self.agent = agent
        self.device_manager = device_manager
        self.obs_logger = obs_logger
        self.confidence = confidence
        self.ws_manager = ws_manager
        self._running = False
        self._task = None

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Autonomous thinking loop started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Autonomous thinking loop stopped")

    async def _loop(self):
        import random
        # Initial delay to let system start
        await asyncio.sleep(30)
        while self._running:
            try:
                if self._is_active_mode():
                    await self._tick()
            except Exception as e:
                logger.error(f"Thinking loop error: {e}", exc_info=True)

            await asyncio.sleep(random.uniform(120, 300))  # 2-5 minutes

    async def _tick(self):
        """One iteration of the thinking loop."""
        context = self._build_context()

        # Check patterns (no LLM needed)
        patterns = await self._get_active_patterns()
        acted = False

        for pattern in patterns:
            if await self._pattern_matches(pattern, context):
                suppressed = await self.confidence.check_denial_match(pattern["id"], context)
                if suppressed:
                    continue

                conf = pattern["confidence"]

                if conf >= AUTO_EXECUTE_THRESHOLD:
                    await self._execute_pattern(pattern, context)
                    acted = True
                elif conf >= SUGGEST_THRESHOLD:
                    await self._suggest_pattern(pattern, context)
                    acted = True

        # Decay patterns periodically
        hour = datetime.utcnow().hour
        if hour == 3:  # Run at 3am UTC
            await self.confidence.apply_decay()

    def _build_context(self) -> dict:
        now = datetime.utcnow()
        return {
            "hour": now.hour,
            "minute": now.minute,
            "day_of_week": now.weekday(),  # 0=Monday, 6=Sunday
            "is_weekend": now.weekday() >= 5,
            "timestamp": now.isoformat(),
        }

    async def _get_active_patterns(self) -> list:
        return await self.confidence.list_patterns(active_only=True)

    async def _pattern_matches(self, pattern: dict, context: dict) -> bool:
        """Check if all pattern conditions match the current context."""
        conditions = pattern.get("conditions", [])
        for condition in conditions:
            cond_type = condition.get("type")

            if cond_type == "hour_range":
                hour = context.get("hour", 0)
                if not (condition["start"] <= hour < condition["end"]):
                    return False

            elif cond_type == "day_type":
                is_weekend = context.get("is_weekend", False)
                if condition["value"] == "weekday" and is_weekend:
                    return False
                if condition["value"] == "weekend" and not is_weekend:
                    return False

            elif cond_type == "day_of_week":
                if context.get("day_of_week") not in condition.get("values", []):
                    return False

        return True

    def _build_pattern_reason(self, pattern: dict, context: dict) -> str:
        """Build a human-readable explanation for why this pattern is being executed."""
        conditions = pattern.get("conditions", [])
        conf = pattern["confidence"]
        trigger_count = pattern.get("trigger_count", 0)
        parts = []

        for cond in conditions:
            ctype = cond.get("type")
            if ctype == "hour_range":
                h = context.get("hour", 0)
                start, end = cond["start"], cond["end"]
                # Format as readable time
                def fmt(hr): return f"{hr % 12 or 12}{'am' if hr < 12 else 'pm'}"
                parts.append(f"it's {fmt(h)} (within your {fmt(start)}–{fmt(end)} window)")
            elif ctype == "day_type":
                day_desc = "weekday" if not context.get("is_weekend") else "weekend"
                parts.append(f"today is a {day_desc} (matching the {cond['value']} condition)")
            elif ctype == "day_of_week":
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                allowed = [days[d] for d in cond.get("values", []) if d < 7]
                parts.append(f"today matches your {'/'.join(allowed)} schedule")

        condition_str = ", and ".join(parts) if parts else "the conditions match"
        confidence_pct = int(conf * 100)
        history_str = f"done this {trigger_count} time{'s' if trigger_count != 1 else ''} before" if trigger_count > 0 else "this is a new pattern"

        return (
            f"Sonus ran '{pattern['name']}' because {condition_str}. "
            f"Confidence is {confidence_pct}% ({history_str})."
        )

    async def _execute_pattern(self, pattern: dict, context: dict):
        """Execute pattern actions automatically and notify user."""
        actions = pattern.get("actions", [])
        executed = []

        for action in actions:
            try:
                device_id = action.get("device_id")
                action_name = action.get("action")
                params = action.get("params", {})

                if device_id and device_id in self.device_manager.devices:
                    device = self.device_manager.devices[device_id]
                    await device.execute_action(action_name, params)
                    executed.append(action)
            except Exception as e:
                logger.error(f"Failed to execute pattern action {action}: {e}")

        if executed:
            logger.info(f"Auto-executed pattern '{pattern['name']}' (confidence: {pattern['confidence']:.2f})")

            # Update trigger count
            async with get_db() as db:
                result = await db.execute(select(Pattern).where(Pattern.id == pattern["id"]))
                p = result.scalar_one_or_none()
                if p:
                    p.trigger_count += 1
                    p.last_triggered = datetime.utcnow()
                    await db.commit()

            reason = self._build_pattern_reason(pattern, context)

            # Notify via WebSocket
            if self.ws_manager:
                await self.ws_manager.broadcast(json.dumps({
                    "type": "autonomous_action",
                    "pattern_id": pattern["id"],
                    "pattern_name": pattern["name"],
                    "actions": executed,
                    "confidence": pattern["confidence"],
                    "reason": reason,
                    "undo_available": True,
                }))

            await self.obs_logger.log(
                obs_type="device_change",
                subject=f"pattern_{pattern['id']}",
                new_value=executed,
                triggered_by="sonus",
                context={"pattern": pattern["name"], "confidence": pattern["confidence"], "reason": reason},
            )

    async def _suggest_pattern(self, pattern: dict, context: dict):
        """Send a suggestion to the user via WebSocket."""
        if self.ws_manager:
            reason = self._build_pattern_reason(pattern, context)
            await self.ws_manager.broadcast(json.dumps({
                "type": "pattern_suggestion",
                "pattern_id": pattern["id"],
                "pattern_name": pattern["name"],
                "description": pattern.get("description", ""),
                "actions": pattern.get("actions", []),
                "confidence": pattern["confidence"],
                "reason": reason,
            }))
            logger.info(f"Suggested pattern '{pattern['name']}' (confidence: {pattern['confidence']:.2f})")
