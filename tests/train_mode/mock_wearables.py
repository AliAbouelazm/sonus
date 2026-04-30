"""
Mock biometric data generators for train-mode tests.

Usage:
    reading = normal_reading()          # Stress=45, HR=68, Battery=80
    reading = high_stress_reading()     # Stress=80, HR=85 — triggers interventions
    stream = stress_escalation_stream() # List of readings over simulated time

These are injected by patching BiometricLoop._fetch_biometrics.
"""
from typing import Optional


# ---------------------------------------------------------------------------
# Single-reading factories
# ---------------------------------------------------------------------------

def normal_reading() -> dict:
    """Calm, well-rested state. No deviations expected."""
    return {
        "heart_rate": 62,
        "stress_level": 35,
        "body_battery": 82,
        "hrv": 58,
        "steps": 3200,
        "sleep_score": 85,
        "source": "garmin",
    }


def high_stress_reading(stress: int = 78, hr: int = 88) -> dict:
    """Elevated stress + HR — should trigger reduce_stress_lighting or cooling_environment."""
    return {
        "heart_rate": hr,
        "stress_level": stress,
        "body_battery": 45,
        "hrv": 32,
        "steps": 5100,
        "sleep_score": 70,
        "source": "garmin",
    }


def exhausted_reading() -> dict:
    """Low battery, low HRV — drained state."""
    return {
        "heart_rate": 72,
        "stress_level": 55,
        "body_battery": 12,
        "hrv": 25,
        "steps": 9800,
        "sleep_score": 55,
        "source": "whoop",
    }


def sleeping_reading() -> dict:
    """Night-time sleeping state."""
    return {
        "heart_rate": 52,
        "stress_level": 10,
        "body_battery": 95,
        "hrv": 72,
        "steps": 50,
        "sleep_score": 92,
        "source": "oura",
    }


def garmin_only() -> dict:
    """Only Garmin fields — for few_integrations tests."""
    return {
        "heart_rate": 65,
        "stress_level": 40,
        "body_battery": 75,
        "hrv": 50,
        "steps": 2400,
        "source": "garmin",
    }


def multi_wearable_merged() -> dict:
    """
    Merged reading as if Garmin + Whoop + Oura + Apple Health all contributed.
    Garmin fills HR/stress, Whoop fills body_battery, Oura fills sleep_score, Apple fills HRV.
    """
    return {
        "heart_rate": 68,         # from garmin
        "stress_level": 42,       # from garmin
        "body_battery": 70,       # from whoop
        "hrv": 55,                # from apple health
        "steps": 4200,            # from garmin
        "sleep_score": 88,        # from oura
        "readiness_score": 82,    # from oura
        "recovery_score": 78,     # from whoop
        "source": "merged",
    }


# ---------------------------------------------------------------------------
# Streams (sequences of readings over simulated time)
# ---------------------------------------------------------------------------

def normal_day_stream(n: int = 5) -> list[dict]:
    """Flat, calm readings — no interventions expected after baselines form."""
    base = normal_reading()
    return [dict(base, steps=base["steps"] + i * 200) for i in range(n)]


def stress_escalation_stream() -> list[dict]:
    """
    Starts normal, gradually escalates to high stress.
    First 3 readings build the baseline, then deviations are detected.
    """
    return [
        {**normal_reading(), "stress_level": 38, "heart_rate": 63},   # tick 1 — baseline
        {**normal_reading(), "stress_level": 40, "heart_rate": 65},   # tick 2 — baseline
        {**normal_reading(), "stress_level": 42, "heart_rate": 64},   # tick 3 — baseline set
        {**normal_reading(), "stress_level": 55, "heart_rate": 70},   # tick 4 — mild rise
        {**normal_reading(), "stress_level": 72, "heart_rate": 82},   # tick 5 — DEVIATION (stress +30 above ~40 baseline)
        {**normal_reading(), "stress_level": 75, "heart_rate": 85},   # tick 6 — still elevated
        {**normal_reading(), "stress_level": 45, "heart_rate": 67},   # tick 7 — recovered
    ]


def hr_spike_stream() -> list[dict]:
    """Heart rate spike stream — triggers cooling_environment."""
    return [
        {**normal_reading(), "heart_rate": 60, "stress_level": 35},   # baseline
        {**normal_reading(), "heart_rate": 62, "stress_level": 36},   # baseline
        {**normal_reading(), "heart_rate": 61, "stress_level": 34},   # baseline set
        {**normal_reading(), "heart_rate": 85, "stress_level": 38},   # HR SPIKE (+23 above ~61)
        {**normal_reading(), "heart_rate": 88, "stress_level": 40},   # still elevated
        {**normal_reading(), "heart_rate": 65, "stress_level": 35},   # recovered
    ]


def multi_wearable_stream(n: int = 6) -> list[dict]:
    """Full multi-wearable merged stream for many_integrations scenarios."""
    readings = []
    for i in range(n):
        base = multi_wearable_merged()
        # Escalate stress on ticks 3-5
        if i >= 3:
            base["stress_level"] = 70 + (i - 3) * 5
            base["heart_rate"] = 80 + (i - 3) * 4
        readings.append(base)
    return readings
