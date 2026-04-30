from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.memory.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceStateRecord(Base):
    __tablename__ = "device_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    integration_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)


class BiometricReading(Base):
    __tablename__ = "biometric_readings"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    heart_rate = mapped_column(Float, nullable=True)
    stress_level = mapped_column(Float, nullable=True)
    body_battery = mapped_column(Float, nullable=True)
    hrv = mapped_column(Float, nullable=True)
    steps = mapped_column(Integer, nullable=True)
    raw_data = mapped_column(JSON, nullable=True)


class BiometricBaseline(Base):
    __tablename__ = "biometric_baselines"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric = mapped_column(String, unique=True, nullable=False)
    baseline_value = mapped_column(Float, nullable=False)
    std_dev = mapped_column(Float, nullable=True)
    sample_count = mapped_column(Integer, default=0)
    last_updated = mapped_column(DateTime, default=datetime.utcnow)


class Observation(Base):
    __tablename__ = "observations"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    obs_type = mapped_column(String, nullable=False)
    subject = mapped_column(String, nullable=True)
    old_value = mapped_column(JSON, nullable=True)
    new_value = mapped_column(JSON, nullable=True)
    triggered_by = mapped_column(String, nullable=True)
    context = mapped_column(JSON, nullable=True)


class Pattern(Base):
    __tablename__ = "patterns"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False)
    description = mapped_column(String, nullable=True)
    conditions = mapped_column(JSON, nullable=False)
    actions = mapped_column(JSON, nullable=False)
    confidence = mapped_column(Float, default=0.3)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    last_triggered = mapped_column(DateTime, nullable=True)
    trigger_count = mapped_column(Integer, default=0)
    last_reinforced = mapped_column(DateTime, nullable=True)
    is_active = mapped_column(Boolean, default=True)
    source = mapped_column(String, default="discovered")


class PatternDenial(Base):
    __tablename__ = "pattern_denials"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern_id = mapped_column(Integer, ForeignKey("patterns.id"), nullable=False)
    denied_at = mapped_column(DateTime, default=datetime.utcnow)
    denial_type = mapped_column(String, nullable=False)
    context_snapshot = mapped_column(JSON, nullable=True)


class Intervention(Base):
    __tablename__ = "interventions"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp = mapped_column(DateTime, default=datetime.utcnow)
    intervention_type = mapped_column(String, nullable=False)
    trigger_metric = mapped_column(String, nullable=True)
    trigger_deviation = mapped_column(Float, nullable=True)
    actions_taken = mapped_column(JSON, nullable=True)
    effectiveness = mapped_column(Float, default=0.5)
    sample_count = mapped_column(Integer, default=0)


class Outcome(Base):
    __tablename__ = "outcomes"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    intervention_id = mapped_column(Integer, ForeignKey("interventions.id"), nullable=True)
    pattern_id = mapped_column(Integer, ForeignKey("patterns.id"), nullable=True)
    triggered_at = mapped_column(DateTime, nullable=False)
    check_at = mapped_column(DateTime, nullable=False)
    checked = mapped_column(Boolean, default=False)
    metric_before = mapped_column(JSON, nullable=True)
    metric_after = mapped_column(JSON, nullable=True)
    action_taken = mapped_column(JSON, nullable=True)
    was_effective = mapped_column(Boolean, nullable=True)
    improvement = mapped_column(Float, nullable=True)


class Experiment(Base):
    __tablename__ = "experiments"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    name = mapped_column(String, nullable=False)
    description = mapped_column(String, nullable=True)
    variable = mapped_column(String, nullable=False)
    values_to_test = mapped_column(JSON, nullable=False)
    outcome_metric = mapped_column(String, nullable=False)
    runs_per_value = mapped_column(Integer, default=3)
    status = mapped_column(String, default="pending")
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    started_at = mapped_column(DateTime, nullable=True)
    completed_at = mapped_column(DateTime, nullable=True)
    current_value_index = mapped_column(Integer, default=0)
    results_summary = mapped_column(JSON, nullable=True)
    optimal_value = mapped_column(JSON, nullable=True)


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id = mapped_column(Integer, ForeignKey("experiments.id"), nullable=False)
    value_tested = mapped_column(JSON, nullable=False)
    run_date = mapped_column(DateTime, nullable=False)
    outcome_value = mapped_column(Float, nullable=True)
    outcome_data = mapped_column(JSON, nullable=True)
    notes = mapped_column(String, nullable=True)
