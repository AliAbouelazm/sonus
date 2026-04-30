"""
End-to-end scenario tests: 'few integrations' and 'many integrations'.

Few  = 1 wearable (Garmin), 2 smart devices, 1 pattern.
Many = 4 wearables merged, 7 smart devices, multiple patterns + experiment.

These test the full pipeline: readings → baseline → deviation → intervention →
thinking loop → confidence adjustment → outcome tracking.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime

from sqlalchemy import select

from backend.app.memory.models import (
    BiometricReading, Intervention, Observation, Pattern, Outcome,
)
from backend.app.memory.database import get_db
from backend.app.intelligence.biometric_loop import BiometricLoop
from backend.app.intelligence.thinking_loop import ThinkingLoop

from .mock_wearables import stress_escalation_stream, multi_wearable_stream, normal_day_stream
from .mock_devices import few_devices, many_devices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_bio_loop(state, dm, intel, readings):
    loop = BiometricLoop(state, dm, intel.obs_logger, intel.outcome_tracker)
    it = iter(readings)
    loop._fetch_biometrics = lambda: __import__("asyncio").coroutine(lambda: next(it, None))()
    # Simpler approach: use a closure that returns next item
    readings_list = list(readings)
    counter = [0]

    async def fetch():
        if counter[0] < len(readings_list):
            r = readings_list[counter[0]]
            counter[0] += 1
            return r
        return None

    loop._fetch_biometrics = fetch
    return loop


def make_think_loop(state, dm, intel):
    return ThinkingLoop(
        app_state=state,
        agent=SimpleNamespace(),
        device_manager=dm,
        obs_logger=intel.obs_logger,
        confidence=intel.confidence,
        ws_manager=intel.ws,
    )


async def seed_intervention(intervention_type: str, effectiveness: float):
    from backend.app.memory.models import Intervention as IM
    async with get_db() as db:
        db.add(IM(
            intervention_type=intervention_type,
            trigger_metric="stress_elevated",
            trigger_deviation=30.0,
            actions_taken=[],
            effectiveness=effectiveness,
            sample_count=10,
        ))
        await db.commit()


async def seed_pattern(name: str, conditions: list, actions: list,
                        confidence: float = 0.90, source: str = "test") -> int:
    async with get_db() as db:
        p = Pattern(name=name, description="", conditions=conditions,
                    actions=actions, confidence=confidence,
                    source=source, is_active=True)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


# ---------------------------------------------------------------------------
# SCENARIO A: Few integrations
# (1 wearable source, 2 devices, 1 pattern, confidence feedback loop)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_few_integrations_normal_day(test_db, make_intelligence):
    """
    Few integrations — calm day.
    5 normal readings should build baselines and produce no interventions.
    """
    dm = few_devices()
    stream = normal_day_stream(5)
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(5):
        await loop._tick()

    async with get_db() as db:
        interventions = (await db.execute(select(Intervention))).scalars().all()
        readings = (await db.execute(select(BiometricReading))).scalars().all()

    assert len(readings) == 5
    assert len(interventions) == 0
    assert dm.all_actions() == []


@pytest.mark.asyncio
async def test_few_integrations_stress_triggers_lighting(test_db, make_intelligence):
    """
    Few integrations — stress escalation.
    High effectiveness pre-seeded → lights should dim and warm automatically.
    """
    dm = few_devices()
    await seed_intervention("reduce_stress_lighting", effectiveness=0.85)

    stream = stress_escalation_stream()
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(len(stream)):
        await loop._tick()

    bulb = dm.devices["living_room_bulb"]
    assert bulb.received_action("set_color_temp"), "Expected warm color temp action"
    assert bulb.received_action("set_brightness"), "Expected dim brightness action"


@pytest.mark.asyncio
async def test_few_integrations_pattern_and_biometric_together(test_db, make_intelligence):
    """
    Few integrations — thinking loop pattern fires alongside biometric intervention.
    Both should execute independently.
    """
    dm = few_devices()
    await seed_intervention("reduce_stress_lighting", effectiveness=0.85)

    # Add a high-confidence evening pattern
    await seed_pattern(
        "Evening AC on",
        conditions=[{"type": "hour_range", "start": 0, "end": 24}],
        actions=[{"device_id": "bedroom_ac", "action": "turn_on", "params": {}}],
        confidence=0.92,
    )

    # Run biometric stream
    stream = stress_escalation_stream()
    bio_loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)
    for _ in range(len(stream)):
        await bio_loop._tick()

    # Run thinking loop tick
    think_loop = make_think_loop(make_intelligence.state, dm, make_intelligence)
    ctx = {"hour": 20, "minute": 0, "day_of_week": 1, "is_weekend": False,
           "timestamp": "2024-01-02T20:00:00"}
    with patch.object(think_loop, "_build_context", return_value=ctx):
        await think_loop._tick()

    # Both should have fired
    assert dm.devices["living_room_bulb"].received_action("set_color_temp")
    assert dm.devices["bedroom_ac"].received_action("turn_on")


@pytest.mark.asyncio
async def test_few_integrations_confidence_feedback_loop(test_db, make_intelligence):
    """
    User approves a pattern → confidence rises → eventually auto-executes.
    Simulates learning over time.
    """
    pid = await seed_pattern("Test feedback",
                              conditions=[{"type": "hour_range", "start": 0, "end": 24}],
                              actions=[{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}],
                              confidence=0.45)  # Below suggest threshold

    # User repeatedly approves — simulating 6 approval signals
    for _ in range(6):
        await make_intelligence.confidence.adjust(pid, "approve")

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()

    # 0.45 + 6*0.08 = 0.93 → should now auto-execute
    assert p.confidence >= 0.85, f"Expected confidence ≥ 0.85, got {p.confidence:.3f}"


# ---------------------------------------------------------------------------
# SCENARIO B: Many integrations
# (4 wearables merged, 7 devices, multiple patterns, experiment, confidence decay)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_many_integrations_merged_biometrics_stored(test_db, make_intelligence):
    """
    Many integrations — merged multi-wearable readings should all be stored.
    """
    dm = many_devices()
    stream = multi_wearable_stream(6)
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(6):
        await loop._tick()

    async with get_db() as db:
        readings = (await db.execute(select(BiometricReading))).scalars().all()

    assert len(readings) == 6
    # Recovery/readiness fields land in raw_data
    assert all(r.stress_level is not None for r in readings)
    assert all(r.heart_rate is not None for r in readings)


@pytest.mark.asyncio
async def test_many_integrations_multiple_lights_dimmed(test_db, make_intelligence):
    """
    Many integrations — stress intervention should dim ALL connected bulbs.
    """
    dm = many_devices()
    await seed_intervention("reduce_stress_lighting", effectiveness=0.88)

    stream = multi_wearable_stream(6)
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(6):
        await loop._tick()

    # All three bulbs should have been acted on
    for bulb_id in ["living_room_bulb", "bedroom_bulb", "office_bulb"]:
        bulb = dm.devices[bulb_id]
        assert bulb.received_action("set_color_temp"), (
            f"{bulb_id} didn't get set_color_temp. Actions: {bulb.actions_log}"
        )


@pytest.mark.asyncio
async def test_many_integrations_cooling_activates_fan_and_ac(test_db, make_intelligence):
    """
    Many integrations — HR spike should activate both AC and fans.
    """
    dm = many_devices()
    await seed_intervention("cooling_environment", effectiveness=0.85)

    from .mock_wearables import hr_spike_stream
    stream = hr_spike_stream()
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(len(stream)):
        await loop._tick()

    ac = dm.devices["bedroom_ac"]
    fan1 = dm.devices["living_room_fan"]
    fan2 = dm.devices["office_fan"]

    assert ac.received_action("turn_on"), "AC should turn on"
    assert fan1.received_action("turn_on") or fan2.received_action("turn_on"), \
        "At least one fan should turn on"


@pytest.mark.asyncio
async def test_many_integrations_multiple_patterns_fire(test_db, make_intelligence):
    """
    Many integrations — 4 patterns for different devices all fire at matching hour.
    """
    dm = many_devices()

    device_actions = [
        ("living_room_bulb",  "set_color_temp", {"temp": "warm"}),
        ("bedroom_bulb",      "turn_on",        {}),
        ("bedroom_ac",        "turn_on",        {}),
        ("living_room_fan",   "turn_on",        {}),
    ]

    for dev_id, action, params in device_actions:
        await seed_pattern(
            f"Night routine - {dev_id}",
            conditions=[{"type": "hour_range", "start": 21, "end": 24}],
            actions=[{"device_id": dev_id, "action": action, "params": params}],
            confidence=0.91,
        )

    think_loop = make_think_loop(make_intelligence.state, dm, make_intelligence)
    ctx = {"hour": 22, "minute": 0, "day_of_week": 2, "is_weekend": False,
           "timestamp": "2024-01-03T22:00:00"}
    with patch.object(think_loop, "_build_context", return_value=ctx):
        await think_loop._tick()

    for dev_id, action, _ in device_actions:
        assert dm.devices[dev_id].received_action(action), (
            f"{dev_id} missing action '{action}'. Log: {dm.devices[dev_id].actions_log}"
        )

    # 4 autonomous_action broadcasts
    auto_actions = [b for b in make_intelligence.ws.broadcasts if "autonomous_action" in str(b)]
    assert len(auto_actions) == 4


@pytest.mark.asyncio
async def test_many_integrations_experiment_lifecycle(test_db, make_intelligence):
    """
    Many integrations — create an experiment, record runs, and check completion.
    """
    result = await make_intelligence.experiment_engine.create_experiment(
        name="Lighting color temp test",
        description="Does warm light reduce stress more than cool?",
        variable="color_temp",
        values_to_test=["2700K", "3500K", "5000K"],
        outcome_metric="stress_reduction",
        runs_per_value=2,
    )
    exp_id = result["id"]
    assert exp_id is not None

    # Must start before runs are counted toward completion
    await make_intelligence.experiment_engine.start_experiment(exp_id)

    # Record 2 runs per value (6 total) — warm light wins
    for temp in ["2700K", "3500K", "5000K"]:
        for run_i in range(2):
            outcome = 0.30 if temp == "2700K" else (0.15 if temp == "3500K" else 0.05)
            await make_intelligence.experiment_engine.record_run_outcome(
                experiment_id=exp_id,
                value_tested=temp,
                outcome_value=outcome + run_i * 0.01,
            )

    # Experiment should now be complete
    experiments = await make_intelligence.experiment_engine.list_experiments()
    exp = next((e for e in experiments if e["id"] == exp_id), None)

    assert exp is not None
    assert exp["status"] == "complete"
    assert exp["optimal_value"] == "2700K"


@pytest.mark.asyncio
async def test_many_integrations_confidence_decay_over_time(test_db, make_intelligence):
    """
    Many integrations — 5 stale patterns all decay together.
    """
    from datetime import timedelta

    stale = datetime.utcnow() - timedelta(weeks=2)
    pids = []
    async with get_db() as db:
        for i in range(5):
            p = Pattern(
                name=f"stale_{i}",
                description="",
                conditions=[],
                actions=[],
                confidence=0.70,
                source="test",
                is_active=True,
                last_reinforced=stale,
            )
            db.add(p)
        await db.commit()

    await make_intelligence.confidence.apply_decay()

    async with get_db() as db:
        result = await db.execute(
            select(Pattern).where(Pattern.name.like("stale_%"))
        )
        patterns = result.scalars().all()

    for p in patterns:
        assert abs(p.confidence - 0.69) < 0.001, (
            f"Pattern {p.name} confidence {p.confidence:.4f} should be ~0.69"
        )


@pytest.mark.asyncio
async def test_many_integrations_observations_logged(test_db, make_intelligence):
    """
    Many integrations — biometric deviations should produce observation records.
    """
    dm = many_devices()
    stream = multi_wearable_stream(6)
    loop = make_bio_loop(make_intelligence.state, dm, make_intelligence, stream)

    for _ in range(6):
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(
            select(Observation).where(Observation.obs_type == "biometric")
        )
        obs = result.scalars().all()

    # Should have logged deviation observations on stress spike ticks
    assert len(obs) >= 1


@pytest.mark.asyncio
async def test_many_integrations_ws_broadcasts_many_patterns(test_db, make_intelligence):
    """
    Many integrations — WebSocket receives one broadcast per pattern execution.
    Mix of auto-execute and suggest-level patterns.
    """
    dm = many_devices()

    # 2 auto-execute patterns (≥0.85)
    await seed_pattern("Auto A", [{"type": "hour_range", "start": 0, "end": 24}],
                        [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}],
                        confidence=0.92)
    await seed_pattern("Auto B", [{"type": "hour_range", "start": 0, "end": 24}],
                        [{"device_id": "bedroom_bulb", "action": "turn_on", "params": {}}],
                        confidence=0.88)

    # 2 suggestion-level patterns (0.50-0.84)
    await seed_pattern("Suggest C", [{"type": "hour_range", "start": 0, "end": 24}],
                        [{"device_id": "bedroom_ac", "action": "turn_on", "params": {}}],
                        confidence=0.65)
    await seed_pattern("Suggest D", [{"type": "hour_range", "start": 0, "end": 24}],
                        [{"device_id": "thermostat", "action": "set_temperature", "params": {"temperature": 22}}],
                        confidence=0.55)

    think_loop = make_think_loop(make_intelligence.state, dm, make_intelligence)
    ctx = {"hour": 12, "minute": 0, "day_of_week": 1, "is_weekend": False,
           "timestamp": "2024-01-02T12:00:00"}
    with patch.object(think_loop, "_build_context", return_value=ctx):
        await think_loop._tick()

    auto = [b for b in make_intelligence.ws.broadcasts if "autonomous_action" in str(b)]
    suggestions = [b for b in make_intelligence.ws.broadcasts if "pattern_suggestion" in str(b)]

    assert len(auto) == 2, f"Expected 2 auto-executes, got {len(auto)}"
    assert len(suggestions) == 2, f"Expected 2 suggestions, got {len(suggestions)}"
