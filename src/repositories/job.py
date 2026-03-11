from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job import Job
from src.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Job, session)
