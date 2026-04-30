"""
Biometric control loop — runs every 30-60 seconds in TRAIN mode only.
Monitors user's health metrics and applies interventions when deviations detected.
Does NOT use the LLM — uses rules and learned effectiveness scores.
"""
import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from ..memory.models import BiometricBaseline, BiometricReading, Intervention
from ..memory.database import get_db
from .observation_logger import ObservationLogger
from .outcome_tracker import OutcomeTracker

logger = logging.getLogger(__name__)

# Deviation thresholds to trigger action
STRESS_DEVIATION_THRESHOLD = 20      # stress points above baseline
BATTERY_DRAIN_THRESHOLD = 0.15       # 15% faster drain than baseline
HR_DEVIATION_THRESHOLD = 15          # BPM above resting baseline
HRV_LOW_THRESHOLD = 15               # ms below baseline (low HRV = more stress/fatigue)
RECOVERY_LOW_ABSOLUTE = 33           # Whoop recovery below 33% = poor
SLEEP_POOR_ABSOLUTE = 60            # Sleep score below 60 = poor
STRAIN_HIGH_ABSOLUTE = 16            # Whoop strain above 16 = high exertion

# Confidence threshold to auto-apply
AUTO_APPLY_THRESHOLD = 0.75
ASK_THRESHOLD = 0.50

class BiometricLoop:
    def __init__(self, app_state, device_manager, obs_logger: ObservationLogger, outcome_tracker: OutcomeTracker, ws_manager=None):
        self.app_state = app_state
        self.device_manager = device_manager
        self.obs_logger = obs_logger
        self.outcome_tracker = outcome_tracker
        self.ws_manager = ws_manager
        self._running = False
        self._task = None

    def _is_active_mode(self) -> bool:
        return getattr(self.app_state, 'mode', 'demo') == 'active'

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Biometric control loop started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Biometric control loop stopped")

    async def _loop(self):
        import random
        while self._running:
            try:
                if self._is_active_mode():
                    await self._tick()
            except Exception as e:
                logger.error(f"Biometric loop error: {e}", exc_info=True)

            # Wait 30-60 seconds (randomized to avoid patterns)
            await asyncio.sleep(random.uniform(30, 60))

    async def _tick(self):
        """One iteration of the biometric loop."""
        reading = await self._fetch_biometrics()
        if not reading:
            return

        await self._store_reading(reading)
        await self._check_pending_outcomes(reading)

        baselines = await self._get_baselines()
        if not baselines:
            # Build initial baselines from this reading
            await self._update_baselines(reading)
            return

        deviations = self._detect_deviations(reading, baselines)
        if not deviations:
            return

        # Log observation
        await self.obs_logger.log(
            obs_type="biometric",
            subject="deviation_detected",
            new_value=deviations,
            context={"reading": reading, "baselines": baselines},
        )

        # Find best intervention
        intervention_type = self._select_intervention(deviations)
        if not intervention_type:
            return

        effectiveness = await self._get_effectiveness(intervention_type)

        if effectiveness >= AUTO_APPLY_THRESHOLD:
            await self._apply_intervention(intervention_type, reading, deviations)
        elif effectiveness >= ASK_THRESHOLD:
            # Autonomous thinking loop will handle asking
            logger.info(f"Biometric deviation detected, intervention {intervention_type} has medium confidence ({effectiveness:.2f}) - deferring to thinking loop")
        else:
            logger.debug(f"Low confidence intervention {intervention_type} ({effectiveness:.2f}) - logging only")

    async def _fetch_biometrics(self) -> Optional[dict]:
        """
        Poll all connected wearables, collect every reading, then merge.

        Each wearable contributes its own field set — they don't all share the
        same schema. For fields that overlap (e.g. HRV from Garmin + Whoop),
        we apply a per-field merge strategy instead of first-wins.
        """
        from ..integrations.config_helper import get_integration_config

        wearable_fetchers = [
            ("garmin",       self._fetch_garmin),
            ("whoop",        self._fetch_whoop),
            ("oura",         self._fetch_oura),
            ("apple_health", self._fetch_apple_health),
        ]

        all_readings = []
        for integration_id, fetcher in wearable_fetchers:
            try:
                cfg = await get_integration_config(integration_id)
                if not cfg:
                    continue
                data = await fetcher(cfg)
                if data:
                    all_readings.append(data)
            except Exception as e:
                logger.debug(f"Could not fetch from {integration_id}: {e}")

        if not all_readings:
            return None
        return self._merge_readings(all_readings)

    def _merge_readings(self, readings: list) -> dict:
        """
        Merge readings from multiple wearables field-by-field.

        Strategy per field type:
          - Physiological signals that should be averaged when multiple sources
            agree (heart_rate, hrv, stress_level, sleep_score, body_battery):
            → average all non-None values
          - Cumulative counters where the highest value wins (steps):
            → max of all values
          - Device-unique fields with no cross-wearable equivalent
            (recovery_score, strain, sleep_efficiency, respiratory_rate,
             readiness_score, avg_heart_rate, resting_hr, …):
            → pass through directly (only one wearable ever provides these)
        """
        AVERAGE_FIELDS = {"heart_rate", "hrv", "stress_level", "sleep_score", "body_battery"}
        MAX_FIELDS = {"steps"}

        # Collect all values per field from all readings
        field_buckets: dict = {}
        for reading in readings:
            for field, value in reading.items():
                if value is not None:
                    field_buckets.setdefault(field, []).append(value)

        merged = {}
        for field, values in field_buckets.items():
            if field in AVERAGE_FIELDS and len(values) > 1:
                # Average across wearables and round to 1 decimal
                merged[field] = round(sum(values) / len(values), 1)
                logger.debug(f"Merged {field} from {len(values)} sources: {values} → {merged[field]}")
            elif field in MAX_FIELDS:
                merged[field] = max(values)
            else:
                # Unique to one wearable — just take the value
                merged[field] = values[0]

        return merged

    async def _fetch_garmin(self, config: dict) -> Optional[dict]:
        """
        Garmin Connect fields:
          heart_rate, stress_level, body_battery, hrv, steps
        """
        try:
            from ..integrations.garmin import GarminIntegration
            garmin = GarminIntegration(config)
            return await garmin.get_current_stats()
        except Exception as e:
            logger.debug(f"Garmin fetch failed: {e}")
            return None

    async def _fetch_whoop(self, config: dict) -> Optional[dict]:
        """
        Whoop Developer API fields:
          heart_rate, hrv, stress_level, body_battery,   ← shared
          recovery_score, strain, avg_heart_rate,         ← Whoop-unique
          sleep_score, sleep_efficiency, respiratory_rate ← Whoop sleep
        """
        try:
            from ..integrations.whoop import WhoopIntegration
            whoop = WhoopIntegration(config)
            return await whoop.get_current_stats()
        except Exception as e:
            logger.debug(f"Whoop fetch failed: {e}")
            return None

    async def _fetch_oura(self, config: dict) -> Optional[dict]:
        """
        Oura Ring v2 API fields:
          hrv, sleep_score,         ← shared with other wearables
          readiness_score           ← Oura-unique (0-100 daily readiness)

        Note: Oura's readiness score is NOT the same as stress level —
        it's a holistic energy/readiness metric. We store it as its own field
        so it doesn't pollute stress_level from Garmin/Whoop.
        """
        try:
            import httpx
            from datetime import date as _date
            token = config.get("token") or config.get("api_key") or config.get("personal_access_token")
            if not token:
                return None
            today = _date.today().isoformat()
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.ouraring.com/v2/usercollection/daily_readiness",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"start_date": today, "end_date": today},
                )
                readiness = r.json().get("data", [{}])[0] if r.is_success else {}

                s = await client.get(
                    "https://api.ouraring.com/v2/usercollection/daily_sleep",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"start_date": today, "end_date": today},
                )
                sleep = s.json().get("data", [{}])[0] if s.is_success else {}

            result = {}
            if readiness.get("score") is not None:
                result["readiness_score"] = readiness["score"]  # Oura-unique
            contrib = readiness.get("contributors", {})
            if contrib.get("hrv_balance") is not None:
                result["hrv"] = contrib["hrv_balance"]
            if sleep.get("score") is not None:
                result["sleep_score"] = sleep["score"]
            return result or None
        except Exception as e:
            logger.debug(f"Oura fetch failed: {e}")
            return None

    async def _fetch_apple_health(self, config: dict) -> Optional[dict]:
        """
        Apple Health snapshot (pushed by iOS Shortcuts / Health Auto Export).
        Fields depend on what the user's shortcut exports — extract everything
        present rather than assuming a fixed schema.

        Typical fields: heart_rate, hrv, steps, sleep_score,
                        resting_heart_rate, active_energy, stand_hours
        """
        try:
            snapshot = config.get("last_snapshot")
            if not snapshot:
                return None
            # Map Apple Health key names → our canonical field names
            APPLE_FIELD_MAP = {
                "heart_rate":          "heart_rate",
                "resting_heart_rate":  "heart_rate",   # prefer resting_heart_rate if present
                "hrv":                 "hrv",
                "heart_rate_variability": "hrv",
                "steps":               "steps",
                "step_count":          "steps",
                "sleep_score":         "sleep_score",
                "body_battery":        "body_battery",
                "respiratory_rate":    "respiratory_rate",
            }
            result = {}
            for apple_key, canonical_key in APPLE_FIELD_MAP.items():
                val = snapshot.get(apple_key)
                if val is not None and canonical_key not in result:
                    result[canonical_key] = val
            return result or None
        except Exception as e:
            logger.debug(f"Apple Health fetch failed: {e}")
            return None

    async def _store_reading(self, reading: dict):
        async with get_db() as db:
            r = BiometricReading(
                heart_rate=reading.get("heart_rate"),
                stress_level=reading.get("stress_level"),
                body_battery=reading.get("body_battery"),
                hrv=reading.get("hrv"),
                steps=reading.get("steps"),
                raw_data=reading,
            )
            db.add(r)
            await db.commit()
        await self._update_baselines(reading)

    async def _get_baselines(self) -> dict:
        async with get_db() as db:
            result = await db.execute(select(BiometricBaseline))
            baselines = result.scalars().all()
        return {b.metric: {"value": b.baseline_value, "std": b.std_dev or 5} for b in baselines}

    async def _update_baselines(self, reading: dict):
        """Update rolling baselines with new reading."""
        async with get_db() as db:
            for metric, value in reading.items():
                if not isinstance(value, (int, float)) or value is None:
                    continue
                result = await db.execute(
                    select(BiometricBaseline).where(BiometricBaseline.metric == metric)
                )
                baseline = result.scalar_one_or_none()
                if baseline is None:
                    baseline = BiometricBaseline(metric=metric, baseline_value=value, sample_count=1)
                    db.add(baseline)
                else:
                    n = baseline.sample_count
                    # Exponential moving average (alpha=0.1)
                    baseline.baseline_value = baseline.baseline_value * 0.9 + value * 0.1
                    baseline.sample_count = n + 1
                    baseline.last_updated = datetime.utcnow()
            await db.commit()

    def _detect_deviations(self, reading: dict, baselines: dict) -> dict:
        deviations = {}

        stress = reading.get("stress_level")
        if stress and "stress_level" in baselines:
            diff = stress - baselines["stress_level"]["value"]
            if diff > STRESS_DEVIATION_THRESHOLD:
                deviations["stress_elevated"] = {"current": stress, "baseline": baselines["stress_level"]["value"], "delta": diff}

        hr = reading.get("heart_rate")
        if hr and "heart_rate" in baselines:
            diff = hr - baselines["heart_rate"]["value"]
            if diff > HR_DEVIATION_THRESHOLD:
                deviations["hr_elevated"] = {"current": hr, "baseline": baselines["heart_rate"]["value"], "delta": diff}

        hrv = reading.get("hrv")
        if hrv and "hrv" in baselines:
            diff = baselines["hrv"]["value"] - hrv  # low HRV = bad
            if diff > HRV_LOW_THRESHOLD:
                deviations["hrv_low"] = {"current": hrv, "baseline": baselines["hrv"]["value"], "delta": diff}

        # Whoop: recovery score (absolute threshold)
        recovery = reading.get("recovery_score")
        if recovery is not None and recovery < RECOVERY_LOW_ABSOLUTE:
            deviations["recovery_low"] = {"current": recovery, "threshold": RECOVERY_LOW_ABSOLUTE}

        # Oura: readiness score (absolute threshold — different concept from Whoop recovery)
        readiness = reading.get("readiness_score")
        if readiness is not None and readiness < RECOVERY_LOW_ABSOLUTE:
            deviations["readiness_low"] = {"current": readiness, "threshold": RECOVERY_LOW_ABSOLUTE}

        # Sleep score — from any wearable that provides it
        sleep_score = reading.get("sleep_score")
        if sleep_score is not None and sleep_score < SLEEP_POOR_ABSOLUTE:
            deviations["sleep_poor"] = {"current": sleep_score, "threshold": SLEEP_POOR_ABSOLUTE}

        # Whoop-specific: strain (0-21 scale, high = heavy exertion)
        strain = reading.get("strain")
        if strain is not None and strain > STRAIN_HIGH_ABSOLUTE:
            deviations["strain_high"] = {"current": strain, "threshold": STRAIN_HIGH_ABSOLUTE}

        return deviations

    def _select_intervention(self, deviations: dict) -> Optional[str]:
        # Priority order: stress > hr > hrv > recovery > sleep > strain
        if "stress_elevated" in deviations:
            return "reduce_stress_lighting"
        if "hr_elevated" in deviations:
            return "cooling_environment"
        if "hrv_low" in deviations:
            return "reduce_stress_lighting"  # Low HRV = same calming response
        if "recovery_low" in deviations or "readiness_low" in deviations or "sleep_poor" in deviations:
            return "recovery_support"
        if "strain_high" in deviations:
            return "cooling_environment"
        return None

    def _build_reason(self, intervention_type: str, deviations: dict, reading: dict) -> str:
        """Build a human-readable explanation for why Sonus is taking this action."""
        parts = []
        if "stress_elevated" in deviations:
            d = deviations["stress_elevated"]
            parts.append(f"stress is {d['current']:.0f} (your baseline is {d['baseline']:.0f}, +{d['delta']:.0f} above normal)")
        if "hr_elevated" in deviations:
            d = deviations["hr_elevated"]
            parts.append(f"heart rate is {d['current']:.0f} bpm (baseline {d['baseline']:.0f}, +{d['delta']:.0f} above normal)")
        if "hrv_low" in deviations:
            d = deviations["hrv_low"]
            parts.append(f"HRV dropped to {d['current']:.0f}ms (normally {d['baseline']:.0f}ms — low HRV signals fatigue or stress)")
        if "recovery_low" in deviations:
            d = deviations["recovery_low"]
            parts.append(f"Whoop recovery is only {d['current']:.0f}% (below the {d['threshold']}% threshold for a good day)")
        if "readiness_low" in deviations:
            d = deviations["readiness_low"]
            parts.append(f"Oura readiness is only {d['current']:.0f}% (below {d['threshold']}% — your body needs rest)")
        if "sleep_poor" in deviations:
            d = deviations["sleep_poor"]
            parts.append(f"sleep score is {d['current']:.0f} (below {d['threshold']} — you didn't sleep well)")
        if "strain_high" in deviations:
            d = deviations["strain_high"]
            parts.append(f"Whoop strain reached {d['current']:.1f}/21 (above {d['threshold']} — high physical exertion)")

        if not parts:
            return f"Biometric deviation detected → applying {intervention_type}"

        action_desc = {
            "reduce_stress_lighting": "dimming lights and warming the color temperature to help you calm down",
            "cooling_environment": "turning on AC and fans to cool you down",
            "recovery_support": "dimming lights and reducing stimulation to support recovery",
        }.get(intervention_type, f"applying {intervention_type}")

        return f"Your {' and '.join(parts)}, so Sonus is {action_desc}."

    async def _get_effectiveness(self, intervention_type: str) -> float:
        async with get_db() as db:
            result = await db.execute(
                select(Intervention).where(
                    Intervention.intervention_type == intervention_type
                ).order_by(Intervention.timestamp.desc()).limit(1)
            )
            intervention = result.scalar_one_or_none()
        return intervention.effectiveness if intervention else 0.5  # default medium confidence

    async def _apply_intervention(self, intervention_type: str, reading: dict, deviations: dict):
        actions = []

        if intervention_type == "reduce_stress_lighting":
            # Set lights to warm, dim
            for device_id, device in self.device_manager.devices.items():
                if hasattr(device, 'execute_action'):
                    try:
                        device_type = type(device).__name__
                        if "Bulb" in device_type:
                            await device.execute_action("set_color_temp", {"temp": "warm"})
                            await device.execute_action("set_brightness", {"brightness": 30})
                            actions.append({"device_id": device_id, "action": "warm_dim"})
                    except Exception as e:
                        logger.debug(f"Could not apply to {device_id}: {e}")

        elif intervention_type == "cooling_environment":
            for device_id, device in self.device_manager.devices.items():
                if hasattr(device, 'execute_action'):
                    try:
                        device_type = type(device).__name__
                        if "AC" in device_type or "Fan" in device_type:
                            await device.execute_action("turn_on", {})
                            actions.append({"device_id": device_id, "action": "turn_on"})
                    except Exception as e:
                        logger.debug(f"Could not apply to {device_id}: {e}")

        elif intervention_type == "recovery_support":
            # Dim all lights and turn off fans to create a calm, low-stimulation environment
            for device_id, device in self.device_manager.devices.items():
                if hasattr(device, 'execute_action'):
                    try:
                        device_type = type(device).__name__
                        if "Bulb" in device_type:
                            await device.execute_action("set_brightness", {"brightness": 20})
                            await device.execute_action("set_color_temp", {"temp": "warm"})
                            actions.append({"device_id": device_id, "action": "recovery_dim"})
                        elif "Fan" in device_type:
                            await device.execute_action("turn_off", {})
                            actions.append({"device_id": device_id, "action": "turn_off"})
                    except Exception as e:
                        logger.debug(f"Could not apply to {device_id}: {e}")

        if not actions:
            return

        reason = self._build_reason(intervention_type, deviations, reading)
        logger.info(f"Applied biometric intervention: {intervention_type} — {reason}")

        # Broadcast to WebSocket with reason
        if self.ws_manager:
            await self.ws_manager.broadcast(json.dumps({
                "type": "biometric_intervention",
                "intervention_type": intervention_type,
                "actions": actions,
                "reason": reason,
                "deviations": deviations,
                "undo_available": True,
            }))

        # Log intervention
        async with get_db() as db:
            intervention = Intervention(
                intervention_type=intervention_type,
                trigger_metric=list(deviations.keys())[0] if deviations else None,
                trigger_deviation=list(deviations.values())[0].get("delta") if deviations else None,
                actions_taken=actions,
            )
            db.add(intervention)
            await db.commit()
            await db.refresh(intervention)

            intervention_id = intervention.id

        # Schedule outcome check
        await self.outcome_tracker.schedule_check(
            action_taken={"type": intervention_type, "actions": actions},
            metric_before={"stress_level": reading.get("stress_level"), "heart_rate": reading.get("heart_rate")},
            check_delay_minutes=10,
            intervention_id=intervention_id,
        )

        await self.obs_logger.log(
            obs_type="device_change",
            subject=intervention_type,
            new_value=actions,
            triggered_by="sonus",
            context={"reason": reason, "deviations": deviations},
        )

    async def _check_pending_outcomes(self, current_reading: dict):
        """Check any pending outcome measurements that are now due."""
        pending = await self.outcome_tracker.get_pending_checks()
        for outcome in pending:
            await self.outcome_tracker.record_result(
                outcome_id=outcome.id,
                metric_after={
                    "stress_level": current_reading.get("stress_level"),
                    "heart_rate": current_reading.get("heart_rate"),
                    "body_battery": current_reading.get("body_battery"),
                },
            )
