from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    async with engine.begin() as conn:
        from backend.app.memory.models import (  # noqa: F401
            Memory, Reminder, DeviceStateRecord, Conversation, IntegrationConfig,
            BiometricReading, BiometricBaseline, Observation, Pattern, PatternDenial,
            Intervention, Outcome, Experiment, ExperimentRun,
        )
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        return session


@asynccontextmanager
async def get_db():
    """Async context manager for database sessions used by intelligence modules."""
    async with async_session() as session:
        yield session
