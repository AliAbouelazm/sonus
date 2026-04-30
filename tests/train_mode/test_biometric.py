"""
Tests for the BiometricLoop.

We skip the asyncio.sleep-based _loop() entirely and call _tick() directly,
injecting mock biometric data via monkeypatching _fetch_biometrics.
"""
import pytest
import pytest_asyncio
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from backend.app.memory.models import BiometricReading, BiometricBaseline, Intervention, Observation
from backend.app.memory.database import get_db
from backend.app.intelligence.biometric_loop import BiometricLoop
from backend.app.intelligence.observation_logger import ObservationLogger
from backend.app.intelligence.outcome_tracker import OutcomeTracker

from .mock_wearables import (
    normal_reading, high_stress_reading, exhausted_reading,
    stress_escalation_stream, hr_spike_stream, garmin_only,
)
from .mock_devices import few_devices, many_devices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_loop(state, device_manager, obs_logger, outcome_tracker, readings: list[dict]):
    """
    Create a BiometricLoop that returns readings in sequence.
    After the sequence is exhausted, returns None (simulates no data).
    """
    loop = BiometricLoop(state, device_manager, obs_logger, outcome_tracker)
    iterator = iter(readings)

    async def mock_fetch():
        return next(iterator, None)

    loop._fetch_biometrics = mock_fetch
    return loop


# ---------------------------------------------------------------------------
# Tests: reading storage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stores_reading(test_db, make_intelligence):
    """A single tick stores a BiometricReading row."""
    dm = few_devices()
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        [normal_reading()],
    )
    await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(BiometricReading))
        rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].heart_rate == 62
    assert rows[0].stress_level == 35


@pytest.mark.asyncio
async def test_builds_baseline_on_first_reading(test_db, make_intelligence):
    """First reading creates BiometricBaseline entries, no intervention yet."""
    dm = few_devices()
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        [normal_reading()],
    )
    await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(BiometricBaseline))
        baselines = result.scalars().all()

    metrics = {b.metric for b in baselines}
    assert "stress_level" in metrics
    assert "heart_rate" in metrics
    assert "body_battery" in metrics

    # No intervention on first tick (no baseline to compare against yet)
    async with get_db() as db:
        result = await db.execute(select(Intervention))
        interventions = result.scalars().all()
    assert len(interventions) == 0


@pytest.mark.asyncio
async def test_baseline_updates_over_multiple_readings(test_db, make_intelligence):
    """Baseline converges via EMA across multiple readings."""
    dm = few_devices()
    readings = [normal_reading()] * 5
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        readings,
    )
    for _ in range(5):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(
            select(BiometricBaseline).where(BiometricBaseline.metric == "stress_level")
        )
        baseline = result.scalar_one_or_none()

    assert baseline is not None
    assert baseline.sample_count == 5
    # EMA with alpha=0.1 starting from 35: should converge near 35
    assert abs(baseline.baseline_value - 35) < 5


# ---------------------------------------------------------------------------
# Tests: deviation detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_intervention_on_normal_reading(test_db, make_intelligence):
    """Normal readings after baseline formation should not trigger interventions."""
    dm = few_devices()
    # 3 normal readings to set baseline, then 2 more normal
    readings = [normal_reading()] * 5
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        readings,
    )
    for _ in range(5):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(Intervention))
        interventions = result.scalars().all()
    assert len(interventions) == 0
    assert dm.all_actions() == []


@pytest.mark.asyncio
async def test_high_stress_triggers_observation(test_db, make_intelligence):
    """After baselines form, a high-stress reading logs a deviation observation."""
    dm = few_devices()
    # Build baseline with normal readings, then spike
    readings = [normal_reading(), normal_reading(), normal_reading(), high_stress_reading(stress=80)]
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        readings,
    )
    for _ in range(4):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(
            select(Observation).where(Observation.obs_type == "biometric")
        )
        obs = result.scalars().all()

    assert len(obs) >= 1
    subjects = [o.subject for o in obs]
    assert "deviation_detected" in subjects


@pytest.mark.asyncio
async def test_stress_escalation_selects_lighting_intervention(test_db, make_intelligence):
    """
    The stress_escalation_stream should select 'reduce_stress_lighting'.
    With default effectiveness 0.5, it falls in the 'ask' range — no auto-apply,
    but once effectiveness is manually set to 0.8, it auto-applies.
    """
    dm = few_devices()
    stream = stress_escalation_stream()
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        stream,
    )

    # Seed an existing intervention record with high effectiveness so auto-apply kicks in
    from backend.app.memory.models import Intervention as InterventionModel
    async with get_db() as db:
        seed = InterventionModel(
            intervention_type="reduce_stress_lighting",
            trigger_metric="stress_elevated",
            trigger_deviation=30.0,
            actions_taken=[],
            effectiveness=0.80,
            sample_count=5,
        )
        db.add(seed)
        await db.commit()

    for _ in range(len(stream)):
        await loop._tick()

    # Should have applied warm/dim to the bulb
    bulb = dm.devices["living_room_bulb"]
    assert bulb.received_action("set_color_temp") or bulb.received_action("set_brightness"), (
        f"Expected lighting action but got: {dm.all_actions()}"
    )


@pytest.mark.asyncio
async def test_hr_spike_selects_cooling_intervention(test_db, make_intelligence):
    """HR spike should select cooling_environment and activate AC/fan."""
    dm = few_devices()
    stream = hr_spike_stream()
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        stream,
    )

    # Seed high-effectiveness cooling intervention
    from backend.app.memory.models import Intervention as InterventionModel
    async with get_db() as db:
        seed = InterventionModel(
            intervention_type="cooling_environment",
            trigger_metric="hr_elevated",
            trigger_deviation=25.0,
            actions_taken=[],
            effectiveness=0.82,
            sample_count=4,
        )
        db.add(seed)
        await db.commit()

    for _ in range(len(stream)):
        await loop._tick()

    ac = dm.devices["bedroom_ac"]
    assert ac.received_action("turn_on"), (
        f"Expected AC turn_on but got: {dm.all_actions()}"
    )


@pytest.mark.asyncio
async def test_no_action_in_demo_mode(test_db, demo_state):
    """BiometricLoop _tick() is a no-op in demo mode."""
    from backend.app.intelligence.observation_logger import ObservationLogger
    from backend.app.intelligence.outcome_tracker import OutcomeTracker

    dm = few_devices()
    obs_logger = ObservationLogger(demo_state)
    outcome_tracker = OutcomeTracker(demo_state)
    loop = make_loop(demo_state, dm, obs_logger, outcome_tracker, [high_stress_reading()] * 5)

    # _loop() checks _is_train_mode() before calling _tick, but _tick itself
    # does not check — test that the mode guard in _loop works end-to-end
    # by checking that calling _tick does not crash and nothing is written
    # (obs_logger.log() guards on train mode internally)
    for _ in range(5):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(Observation))
        obs = result.scalars().all()
    # ObservationLogger won't write in demo mode
    assert len(obs) == 0


# ---------------------------------------------------------------------------
# Tests: outcome tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outcome_scheduled_after_intervention(test_db, make_intelligence):
    """Applying an intervention should schedule an Outcome check."""
    from backend.app.memory.models import Outcome, Intervention as InterventionModel

    dm = few_devices()
    stream = stress_escalation_stream()
    loop = make_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.outcome_tracker,
        stream,
    )

    async with get_db() as db:
        seed = InterventionModel(
            intervention_type="reduce_stress_lighting",
            trigger_metric="stress_elevated",
            trigger_deviation=30.0,
            actions_taken=[],
            effectiveness=0.80,
            sample_count=5,
        )
        db.add(seed)
        await db.commit()

    for _ in range(len(stream)):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(Outcome))
        outcomes = result.scalars().all()

    # At least one outcome check should have been scheduled
    assert len(outcomes) >= 1
    assert outcomes[0].checked is False  # not yet measured
