"""
CLI simulation runner for Sonus train mode.

Run a full scenario without pytest — useful for visual inspection of what
the system does step by step. Uses an isolated temp DB, never touches sonus.db.

Usage:
    python tests/train_mode/simulate.py                 # default: stress scenario, few integrations
    python tests/train_mode/simulate.py --mode few      # 1 wearable, 2 devices
    python tests/train_mode/simulate.py --mode many     # 4 wearables merged, 7 devices
    python tests/train_mode/simulate.py --scenario hr   # HR spike scenario
    python tests/train_mode/simulate.py --mode many --scenario stress
"""
import argparse
import asyncio
import sys
import os
import tempfile
import json
from types import SimpleNamespace
from datetime import datetime
from contextlib import asynccontextmanager

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------------------------------------------------------------------------
# ANSI colours for terminal output
# ---------------------------------------------------------------------------
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def header(text):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")


def step(tick: int, reading: dict):
    stress = reading.get("stress_level", "?")
    hr = reading.get("heart_rate", "?")
    batt = reading.get("body_battery", "?")
    src = reading.get("source", "unknown")
    print(f"\n{BOLD}[Tick {tick:02d}]{RESET} stress={stress} hr={hr} battery={batt} source={src}")


def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚡{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def err(msg):   print(f"  {RED}✗{RESET} {msg}")


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

async def run_simulation(mode: str, scenario: str):
    # Import after path setup
    from mock_wearables import (
        stress_escalation_stream, hr_spike_stream,
        multi_wearable_stream, normal_day_stream,
    )
    from mock_devices import few_devices, many_devices

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    import backend.app.memory.models  # noqa
    from backend.app.memory.database import Base
    from backend.app.intelligence.biometric_loop import BiometricLoop
    from backend.app.intelligence.thinking_loop import ThinkingLoop
    from backend.app.intelligence.observation_logger import ObservationLogger
    from backend.app.intelligence.outcome_tracker import OutcomeTracker
    from backend.app.intelligence.confidence import ConfidenceSystem
    from backend.app.intelligence.experiment_engine import ExperimentEngine
    from sqlalchemy import select
    from backend.app.memory.models import (
        BiometricReading, BiometricBaseline, Intervention,
        Observation, Pattern, Outcome,
    )

    # ── Temp DB ──
    tmp = tempfile.mkdtemp(prefix="sonus_sim_")
    db_path = os.path.join(tmp, "sim.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Patch the global session factory
    import backend.app.memory.database as db_module
    orig_session = db_module.async_session
    db_module.async_session = session_factory

    @asynccontextmanager
    async def get_db():
        async with session_factory() as s:
            yield s

    state = SimpleNamespace(mode="train")

    # ── WebSocket mock ──
    ws_broadcasts = []
    ws = SimpleNamespace(broadcasts=ws_broadcasts)
    async def ws_broadcast(msg):
        ws_broadcasts.append(msg)
    ws.broadcast = ws_broadcast

    # ── Devices ──
    dm = many_devices() if mode == "many" else few_devices()

    # ── Intelligence ──
    obs_logger     = ObservationLogger(state)
    outcome_tracker = OutcomeTracker(state)
    confidence     = ConfidenceSystem(state)
    exp_engine     = ExperimentEngine(state)

    # ── Stream ──
    if scenario == "hr":
        stream = hr_spike_stream()
        stream_label = "HR Spike"
    elif scenario == "calm":
        stream = normal_day_stream(6)
        stream_label = "Calm Day"
    else:  # default: stress
        stream = multi_wearable_stream(6) if mode == "many" else stress_escalation_stream()
        stream_label = "Stress Escalation"

    # ── Seed high-effectiveness interventions so auto-apply triggers ──
    from backend.app.memory.models import Intervention as IM
    async with session_factory() as db:
        db.add(IM(intervention_type="reduce_stress_lighting",
                  trigger_metric="stress_elevated", trigger_deviation=25.0,
                  actions_taken=[], effectiveness=0.85, sample_count=8))
        db.add(IM(intervention_type="cooling_environment",
                  trigger_metric="hr_elevated", trigger_deviation=20.0,
                  actions_taken=[], effectiveness=0.82, sample_count=6))
        await db.commit()

    # ── Seed patterns ──
    patterns_to_add = [
        ("Evening lights dim", [{"type": "hour_range", "start": 18, "end": 23}],
         [{"device_id": "living_room_bulb", "action": "set_color_temp", "params": {"temp": "warm"}}],
         0.91),
    ]
    if mode == "many":
        patterns_to_add += [
            ("Night AC on", [{"type": "hour_range", "start": 21, "end": 24}],
             [{"device_id": "bedroom_ac", "action": "turn_on", "params": {}}], 0.88),
            ("Office fan on hot days", [{"type": "hour_range", "start": 10, "end": 18}],
             [{"device_id": "office_fan", "action": "turn_on", "params": {}}], 0.60),  # suggest-only
            ("Uncertain morning", [{"type": "hour_range", "start": 6, "end": 9}],
             [{"device_id": "bedroom_bulb", "action": "turn_on", "params": {}}], 0.35),  # too low
        ]

    async with session_factory() as db:
        for name, cond, acts, conf in patterns_to_add:
            db.add(Pattern(name=name, description="", conditions=cond, actions=acts,
                            confidence=conf, source="seeded", is_active=True))
        await db.commit()

    # ── Run biometric simulation ──
    header(f"SONUS TRAIN MODE SIMULATION — {mode.upper()} / {stream_label}")
    print(f"  Devices : {list(dm.devices.keys())}")
    print(f"  Readings: {len(stream)} ticks")

    readings_list = list(stream)
    counter = [0]

    async def fetch():
        if counter[0] < len(readings_list):
            r = readings_list[counter[0]]
            counter[0] += 1
            return r
        return None

    bio_loop = BiometricLoop(state, dm, obs_logger, outcome_tracker)
    bio_loop._fetch_biometrics = fetch

    print(f"\n{BOLD}── Biometric Loop ──{RESET}")
    for tick in range(len(stream)):
        step(tick + 1, readings_list[tick])
        await bio_loop._tick()

        # Show what happened
        async with session_factory() as db:
            interventions = (await db.execute(
                select(IM).order_by(IM.timestamp.desc()).limit(1)
            )).scalars().all()
            obs = (await db.execute(
                select(Observation).where(Observation.obs_type == "biometric")
                .order_by(Observation.timestamp.desc()).limit(1)
            )).scalars().all()

        for o in obs:
            if o.subject == "deviation_detected":
                warn(f"Deviation detected: {o.new_value}")

        device_actions = dm.all_actions()
        if device_actions:
            for a in device_actions[-3:]:  # show last 3
                ok(f"Device action → {a['device_id']}: {a['action']} {a.get('params', '')}")

    # ── Run thinking loop (simulate one tick at hour 19 on a weekday) ──
    print(f"\n{BOLD}── Thinking Loop (simulated at 19:00 weekday) ──{RESET}")
    mock_agent = SimpleNamespace()
    think_loop = ThinkingLoop(state, mock_agent, dm, obs_logger, confidence, ws)

    from unittest.mock import patch as mock_patch
    ctx = {"hour": 19, "minute": 0, "day_of_week": 1,
           "is_weekend": False, "timestamp": datetime.utcnow().isoformat()}
    with mock_patch.object(think_loop, "_build_context", return_value=ctx):
        await think_loop._tick()

    for b in ws_broadcasts:
        parsed = json.loads(b) if isinstance(b, str) else b
        msg_type = parsed.get("type", "?")
        name = parsed.get("pattern_name", "")
        conf = parsed.get("confidence", "?")
        if msg_type == "autonomous_action":
            ok(f"AUTO-EXECUTED: '{name}' (confidence {conf:.2f})")
        elif msg_type == "pattern_suggestion":
            warn(f"SUGGESTED: '{name}' (confidence {conf:.2f})")

    # ── Summary ──
    header("SIMULATION SUMMARY")

    async with session_factory() as db:
        n_readings     = (await db.execute(select(BiometricReading))).scalars().all()
        n_baselines    = (await db.execute(select(BiometricBaseline))).scalars().all()
        n_interventions = (await db.execute(select(IM))).scalars().all()
        n_obs          = (await db.execute(select(Observation))).scalars().all()
        n_outcomes     = (await db.execute(select(Outcome))).scalars().all()

    info(f"Readings stored       : {len(n_readings)}")
    info(f"Baselines built       : {len(n_baselines)} metrics")
    info(f"Interventions logged  : {len([i for i in n_interventions if i.sample_count is None or i.sample_count <= 1])}")
    info(f"Observations logged   : {len(n_obs)}")
    info(f"Outcome checks pending: {len([o for o in n_outcomes if not o.checked])}")

    total_device_actions = len(dm.all_actions())
    info(f"Device actions taken  : {total_device_actions}")

    auto_broadcasts  = [b for b in ws_broadcasts if "autonomous_action" in str(b)]
    suggest_broadcasts = [b for b in ws_broadcasts if "pattern_suggestion" in str(b)]
    info(f"WS auto-executes sent : {len(auto_broadcasts)}")
    info(f"WS suggestions sent   : {len(suggest_broadcasts)}")

    if total_device_actions == 0 and not auto_broadcasts:
        warn("No actions taken — try a stress/hr scenario with --scenario stress or --scenario hr")

    # Cleanup
    db_module.async_session = orig_session
    await engine.dispose()

    print(f"\n{BOLD}Temp DB:{RESET} {db_path}")
    print(f"{BOLD}Done.{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Sonus train mode simulator")
    parser.add_argument("--mode", choices=["few", "many"], default="few",
                        help="few=1 wearable+2 devices, many=4 wearables+7 devices (default: few)")
    parser.add_argument("--scenario", choices=["stress", "hr", "calm"], default="stress",
                        help="stress=escalation, hr=spike, calm=normal day (default: stress)")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.mode, args.scenario))


if __name__ == "__main__":
    # Add the tests/train_mode directory itself to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    main()
