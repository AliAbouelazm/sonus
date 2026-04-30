"""
Tests for the ThinkingLoop and ConfidenceSystem.

We call _tick() directly with a mocked context (custom hour/day_of_week)
to test pattern matching without waiting for real time.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from types import SimpleNamespace

from sqlalchemy import select
from backend.app.memory.models import Pattern, PatternDenial
from backend.app.memory.database import get_db
from backend.app.intelligence.thinking_loop import ThinkingLoop
from backend.app.intelligence.confidence import ConfidenceSystem
from backend.app.intelligence.observation_logger import ObservationLogger

from .mock_devices import few_devices, many_devices


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def add_pattern(db, name: str, conditions: list, actions: list,
                       confidence: float = 0.6, source: str = "test") -> int:
    p = Pattern(
        name=name,
        description=f"Test pattern: {name}",
        conditions=conditions,
        actions=actions,
        confidence=confidence,
        source=source,
        is_active=True,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p.id


def make_thinking_loop(state, device_manager, obs_logger, confidence, ws):
    """Create ThinkingLoop with a mocked agent (not used in pattern matching)."""
    mock_agent = SimpleNamespace()
    return ThinkingLoop(
        app_state=state,
        agent=mock_agent,
        device_manager=device_manager,
        obs_logger=obs_logger,
        confidence=confidence,
        ws_manager=ws,
    )


# ---------------------------------------------------------------------------
# Tests: pattern matching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_patterns_no_actions(test_db, make_intelligence):
    """Empty pattern table — nothing should execute."""
    dm = few_devices()
    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )
    await loop._tick()
    assert dm.all_actions() == []
    assert make_intelligence.ws.broadcasts == []


@pytest.mark.asyncio
async def test_pattern_matches_hour_range(test_db, make_intelligence):
    """Pattern with hour_range condition executes when context hour is in range."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        await add_pattern(db, "Evening lights",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=actions, confidence=0.90)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    # Inject context: hour=19 (within range), weekday
    with patch.object(loop, "_build_context", return_value={"hour": 19, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T19:00:00"}):
        await loop._tick()

    assert dm.devices["living_room_bulb"].received_action("turn_on")
    # Should broadcast autonomous_action
    assert any("autonomous_action" in str(b) for b in make_intelligence.ws.broadcasts)


@pytest.mark.asyncio
async def test_pattern_does_not_match_outside_hour_range(test_db, make_intelligence):
    """Pattern does not execute when context hour is outside the hour_range."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        await add_pattern(db, "Evening lights",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=actions, confidence=0.90)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    # hour=10 — outside 17-22
    with patch.object(loop, "_build_context", return_value={"hour": 10, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T10:00:00"}):
        await loop._tick()

    assert not dm.devices["living_room_bulb"].received_action("turn_on")


@pytest.mark.asyncio
async def test_weekday_pattern_skips_weekend(test_db, make_intelligence):
    """day_type=weekday pattern does not fire on weekend."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        await add_pattern(db, "Weekday morning",
                          conditions=[
                              {"type": "hour_range", "start": 7, "end": 9},
                              {"type": "day_type", "value": "weekday"},
                          ],
                          actions=actions, confidence=0.90)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    # Saturday morning
    with patch.object(loop, "_build_context", return_value={"hour": 8, "minute": 0,
                                                              "day_of_week": 5, "is_weekend": True,
                                                              "timestamp": "2024-01-06T08:00:00"}):
        await loop._tick()

    assert not dm.devices["living_room_bulb"].received_action("turn_on")


@pytest.mark.asyncio
async def test_suggestion_sent_for_medium_confidence_pattern(test_db, make_intelligence):
    """Pattern with confidence 0.55-0.84 sends a suggestion, not auto-execute."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        await add_pattern(db, "Maybe evening lights",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=actions, confidence=0.60)  # below AUTO_EXECUTE_THRESHOLD (0.85)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    with patch.object(loop, "_build_context", return_value={"hour": 19, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T19:00:00"}):
        await loop._tick()

    # Device should NOT be touched
    assert not dm.devices["living_room_bulb"].received_action("turn_on")
    # But a suggestion should have been broadcast
    assert any("pattern_suggestion" in str(b) for b in make_intelligence.ws.broadcasts)


@pytest.mark.asyncio
async def test_low_confidence_pattern_ignored(test_db, make_intelligence):
    """Pattern below SUGGEST_THRESHOLD (0.50) — no action, no suggestion."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        await add_pattern(db, "Uncertain lights",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=actions, confidence=0.30)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    with patch.object(loop, "_build_context", return_value={"hour": 19, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T19:00:00"}):
        await loop._tick()

    assert dm.all_actions() == []
    assert make_intelligence.ws.broadcasts == []


# ---------------------------------------------------------------------------
# Tests: denial suppression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denied_pattern_suppressed_in_same_context(test_db, make_intelligence):
    """After user says 'no', the pattern is suppressed in the same hour context."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        pid = await add_pattern(db, "Evening lights",
                                conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                                actions=actions, confidence=0.90)

    # Record a denial at hour=19 on a weekday
    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 19, "is_weekend": False})

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    # Try at hour=19 again — should be suppressed
    with patch.object(loop, "_build_context", return_value={"hour": 19, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T19:00:00"}):
        await loop._tick()

    assert not dm.devices["living_room_bulb"].received_action("turn_on")


@pytest.mark.asyncio
async def test_denied_pattern_runs_at_different_hour(test_db, make_intelligence):
    """Denial at hour=19 should not suppress the pattern at hour=21."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        # Start at 0.98 so after 'no' (-0.12) confidence lands at 0.86 — still above AUTO_EXECUTE_THRESHOLD (0.85)
        pid = await add_pattern(db, "Evening lights",
                                conditions=[{"type": "hour_range", "start": 17, "end": 23}],
                                actions=actions, confidence=0.98)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 19, "is_weekend": False})

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    # Hour=21 — more than 1 hour from denied hour=19, should execute
    with patch.object(loop, "_build_context", return_value={"hour": 21, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T21:00:00"}):
        await loop._tick()

    assert dm.devices["living_room_bulb"].received_action("turn_on")


# ---------------------------------------------------------------------------
# Tests: multiple patterns + devices
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_patterns_execute_independently(test_db, make_intelligence):
    """Multiple matching patterns each execute their own actions."""
    dm = many_devices()

    async with get_db() as db:
        await add_pattern(db, "Evening main light",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=[{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}],
                          confidence=0.90)
        await add_pattern(db, "Evening bedroom light",
                          conditions=[{"type": "hour_range", "start": 17, "end": 22}],
                          actions=[{"device_id": "bedroom_bulb", "action": "turn_on", "params": {}}],
                          confidence=0.92)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    with patch.object(loop, "_build_context", return_value={"hour": 19, "minute": 0,
                                                              "day_of_week": 1, "is_weekend": False,
                                                              "timestamp": "2024-01-02T19:00:00"}):
        await loop._tick()

    assert dm.devices["living_room_bulb"].received_action("turn_on")
    assert dm.devices["bedroom_bulb"].received_action("turn_on")


@pytest.mark.asyncio
async def test_trigger_count_increments(test_db, make_intelligence):
    """Each pattern execution increments trigger_count in the DB."""
    dm = few_devices()
    actions = [{"device_id": "living_room_bulb", "action": "turn_on", "params": {}}]

    async with get_db() as db:
        pid = await add_pattern(db, "Counted pattern",
                                conditions=[{"type": "hour_range", "start": 0, "end": 24}],
                                actions=actions, confidence=0.90)

    loop = make_thinking_loop(
        make_intelligence.state, dm,
        make_intelligence.obs_logger, make_intelligence.confidence,
        make_intelligence.ws,
    )

    ctx = {"hour": 12, "minute": 0, "day_of_week": 1, "is_weekend": False, "timestamp": "2024-01-02T12:00:00"}
    with patch.object(loop, "_build_context", return_value=ctx):
        await loop._tick()
        dm.clear_all_logs()
        await loop._tick()

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()

    assert p.trigger_count == 2
