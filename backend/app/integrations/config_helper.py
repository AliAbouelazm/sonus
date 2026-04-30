"""Helper to look up integration configs stored in the DB by the UI."""
from typing import Optional

from sqlalchemy import select

from backend.app.memory.database import async_session
from backend.app.memory.models import IntegrationConfig


async def get_integration_config(integration_id: str) -> Optional[dict]:
    """Return the config dict for the first connected instance of an integration."""
    async with async_session() as session:
        result = await session.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.integration_id == integration_id,
                IntegrationConfig.is_connected == True,  # noqa: E712
            )
        )
        record = result.scalar_one_or_none()
        if record and record.config:
            return record.config
        return None
