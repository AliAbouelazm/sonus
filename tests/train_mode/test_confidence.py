"""
Tests for the ConfidenceSystem — signal adjustments, clamping, and decay.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy import select

from backend.app.memory.models import Pattern, PatternDenial
from backend.app.memory.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_pattern(db, name: str, confidence: float = 0.5,
                          last_reinforced: datetime = None) -> int:
    p = Pattern(
        name=name,
        description="",
        conditions=[],
        actions=[],
        confidence=confidence,
        source="test",
        is_active=True,
        last_reinforced=last_reinforced or datetime.utcnow(),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p.id


# ---------------------------------------------------------------------------
# Tests: signal adjustments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_increases_confidence(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "approve")

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert abs(p.confidence - 0.58) < 0.001


@pytest.mark.asyncio
async def test_always_gives_large_boost(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "always")

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert abs(p.confidence - 0.75) < 0.001


@pytest.mark.asyncio
async def test_no_decreases_confidence(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 14, "is_weekend": False})

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert abs(p.confidence - 0.38) < 0.001


@pytest.mark.asyncio
async def test_never_destroys_confidence(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "never")

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert abs(p.confidence - 0.10) < 0.001


@pytest.mark.asyncio
async def test_undo_fast_large_penalty(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "undo_fast", context={"hour": 20, "is_weekend": False})

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert abs(p.confidence - 0.25) < 0.001


@pytest.mark.asyncio
async def test_confidence_clamped_at_1(test_db, make_intelligence):
    """Cannot exceed 1.0."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.95)

    await make_intelligence.confidence.adjust(pid, "approve")  # +0.08

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert p.confidence <= 1.0


@pytest.mark.asyncio
async def test_confidence_clamped_at_0(test_db, make_intelligence):
    """Cannot go below 0.0."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.05)

    await make_intelligence.confidence.adjust(pid, "never")  # -0.40

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert p.confidence >= 0.0


@pytest.mark.asyncio
async def test_multiple_approvals_accumulate(test_db, make_intelligence):
    """Ten approvals should substantially raise confidence."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.3)

    for _ in range(10):
        await make_intelligence.confidence.adjust(pid, "approve")

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()
    assert p.confidence > 0.8


# ---------------------------------------------------------------------------
# Tests: denial recording
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denial_recorded_for_no_signal(test_db, make_intelligence):
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 15, "is_weekend": False})

    async with get_db() as db:
        result = await db.execute(
            select(PatternDenial).where(PatternDenial.pattern_id == pid)
        )
        denials = result.scalars().all()

    assert len(denials) == 1
    assert denials[0].denial_type == "no"


@pytest.mark.asyncio
async def test_no_denial_for_approve_signal(test_db, make_intelligence):
    """Positive signals don't create PatternDenial records."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "approve")

    async with get_db() as db:
        result = await db.execute(
            select(PatternDenial).where(PatternDenial.pattern_id == pid)
        )
        denials = result.scalars().all()

    assert len(denials) == 0


# ---------------------------------------------------------------------------
# Tests: decay
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decay_applied_to_stale_patterns(test_db, make_intelligence):
    """Patterns not reinforced in >1 week should lose 1% confidence."""
    old_reinforced = datetime.utcnow() - timedelta(weeks=2)

    async with get_db() as db:
        pid = await create_pattern(db, "stale_pattern", confidence=0.70,
                                    last_reinforced=old_reinforced)

    await make_intelligence.confidence.apply_decay()

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()

    assert abs(p.confidence - 0.69) < 0.001


@pytest.mark.asyncio
async def test_no_decay_for_recently_reinforced(test_db, make_intelligence):
    """Patterns reinforced within the last week are not decayed."""
    async with get_db() as db:
        pid = await create_pattern(db, "fresh_pattern", confidence=0.70,
                                    last_reinforced=datetime.utcnow())

    await make_intelligence.confidence.apply_decay()

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()

    assert abs(p.confidence - 0.70) < 0.001


@pytest.mark.asyncio
async def test_decay_does_not_run_in_demo_mode(test_db, demo_state):
    """Decay is a no-op in demo mode."""
    from backend.app.intelligence.confidence import ConfidenceSystem

    old_reinforced = datetime.utcnow() - timedelta(weeks=2)
    async with get_db() as db:
        pid = await create_pattern(db, "stale_demo", confidence=0.70,
                                    last_reinforced=old_reinforced)

    confidence = ConfidenceSystem(demo_state)
    await confidence.apply_decay()

    async with get_db() as db:
        result = await db.execute(select(Pattern).where(Pattern.id == pid))
        p = result.scalar_one()

    # Should be unchanged
    assert abs(p.confidence - 0.70) < 0.001


# ---------------------------------------------------------------------------
# Tests: check_denial_match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denial_match_same_hour(test_db, make_intelligence):
    """check_denial_match returns True when denied in same hour ±1."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 19, "is_weekend": False})

    suppressed = await make_intelligence.confidence.check_denial_match(
        pid, {"hour": 19, "is_weekend": False}
    )
    assert suppressed is True


@pytest.mark.asyncio
async def test_denial_match_within_1_hour(test_db, make_intelligence):
    """Denial at hour 19 suppresses at hour 18 and 20 (within ±1)."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 19, "is_weekend": False})

    for check_hour in [18, 20]:
        suppressed = await make_intelligence.confidence.check_denial_match(
            pid, {"hour": check_hour, "is_weekend": False}
        )
        assert suppressed is True, f"Expected suppression at hour {check_hour}"


@pytest.mark.asyncio
async def test_denial_match_far_hour_not_suppressed(test_db, make_intelligence):
    """Denial at hour 19 does not suppress at hour 10 (more than ±1 away)."""
    async with get_db() as db:
        pid = await create_pattern(db, "test", confidence=0.5)

    await make_intelligence.confidence.adjust(pid, "no", context={"hour": 19, "is_weekend": False})

    suppressed = await make_intelligence.confidence.check_denial_match(
        pid, {"hour": 10, "is_weekend": False}
    )
    assert suppressed is False
