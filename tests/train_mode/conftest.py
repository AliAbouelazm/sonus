"""
Shared pytest fixtures for train-mode tests.

Key trick: we patch backend.app.memory.database.async_session at the module level.
get_db() calls async_session() at runtime (not import time), so replacing the module
attribute makes ALL get_db() calls — even in already-imported modules — use the test DB.
"""
import sys
import os
import json
import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# Colour helpers (no deps)
# ---------------------------------------------------------------------------
_C = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "magenta":"\033[95m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}

def _c(colour, text):
    return f"{_C[colour]}{text}{_C['reset']}"


def _print_msg(msg_str: str):
    """Pretty-print one WebSocket broadcast."""
    try:
        msg = json.loads(msg_str) if isinstance(msg_str, str) else msg_str
    except Exception:
        print(f"  {_c('dim', msg_str)}")
        return

    t = msg.get("type", "?")
    if t == "autonomous_action":
        conf = msg.get("confidence", 0)
        conf_str = f"{conf:.2f}" if isinstance(conf, float) else str(conf)
        pname = repr(msg.get("pattern_name", "?"))
        print(
            f"  {_c('bold', '🤖 WS autonomous_action')}  "
            f"pattern={_c('green', pname)}  "
            f"confidence={_c('cyan', conf_str)}"
        )
        for a in msg.get("actions", []):
            dev = _c("yellow", a.get("device_id", "?"))
            act = _c("green", a.get("action", "?"))
            print(f"      {_c('dim', 'device=')} {dev}  {_c('dim', 'action=')} {act}  params={a.get('params', {})}")
    elif t == "pattern_suggestion":
        conf = msg.get("confidence", 0)
        conf_str = f"{conf:.2f}" if isinstance(conf, float) else str(conf)
        pname = repr(msg.get("pattern_name", "?"))
        print(
            f"  {_c('bold', '💡 WS pattern_suggestion')}  "
            f"pattern={_c('yellow', pname)}  "
            f"confidence={_c('cyan', conf_str)}"
        )
    else:
        print(f"  {_c('dim', 'WS')} {t}: {msg}")


# ---------------------------------------------------------------------------
# In-memory SQLite DB (per-test isolation via tmp_path)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_db(tmp_path):
    """
    Creates a fresh SQLite DB in a temp file, patches the global async_session
    so every get_db() call in every intelligence module uses this test DB.
    Yields the engine; tears down after the test.
    """
    db_path = tmp_path / "sonus_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    # Import all models so SQLAlchemy knows about the tables
    import backend.app.memory.models  # noqa: F401
    from backend.app.memory.database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Patch the module-level async_session — get_db() will pick this up
    import backend.app.memory.database as db_module
    original_session = db_module.async_session
    db_module.async_session = test_session_factory

    yield engine

    # Restore
    db_module.async_session = original_session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Mock app state
# ---------------------------------------------------------------------------

@pytest.fixture
def train_state():
    """Minimal app_state namespace in TRAIN mode."""
    return SimpleNamespace(mode="train")


@pytest.fixture
def demo_state():
    """Minimal app_state namespace in DEMO mode."""
    return SimpleNamespace(mode="demo")


# ---------------------------------------------------------------------------
# Mock WebSocket manager
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ws():
    """Records and live-prints every broadcast() call."""
    ws = SimpleNamespace(broadcasts=[])

    async def broadcast(msg):
        ws.broadcasts.append(msg)
        _print_msg(msg)

    ws.broadcast = broadcast
    return ws


# ---------------------------------------------------------------------------
# pytest hook: print per-test header + summary of WS messages + device actions
# ---------------------------------------------------------------------------

def pytest_runtest_protocol(item, nextitem):
    """Print a visible separator before each test."""
    print(f"\n{_c('bold', '─' * 64)}")
    print(f"{_c('bold', '▶ TEST:')} {_c('cyan', item.name)}")
    return None  # let pytest handle the rest normally


# ---------------------------------------------------------------------------
# Intelligence component factories (require test_db to be active)
# ---------------------------------------------------------------------------

@pytest.fixture
def make_intelligence(test_db, train_state, mock_ws):
    """
    Factory that creates all intelligence components wired together,
    using the patched test DB and train_state.
    """
    from backend.app.intelligence.observation_logger import ObservationLogger
    from backend.app.intelligence.outcome_tracker import OutcomeTracker
    from backend.app.intelligence.confidence import ConfidenceSystem
    from backend.app.intelligence.experiment_engine import ExperimentEngine
    from backend.app.intelligence.local_models import LocalModelTrainer

    obs_logger = ObservationLogger(train_state)
    outcome_tracker = OutcomeTracker(train_state)
    confidence = ConfidenceSystem(train_state)
    experiment_engine = ExperimentEngine(train_state)
    local_trainer = LocalModelTrainer(train_state)

    return SimpleNamespace(
        state=train_state,
        obs_logger=obs_logger,
        outcome_tracker=outcome_tracker,
        confidence=confidence,
        experiment_engine=experiment_engine,
        local_trainer=local_trainer,
        ws=mock_ws,
    )
