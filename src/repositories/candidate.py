from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.candidate import Candidate
from src.repositories.base import BaseRepository


class CandidateRepository(BaseRepository[Candidate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Candidate, session)

    async def get_by_email(self, email: str) -> Optional[Candidate]:
        result = await self.session.execute(
            select(Candidate).where(Candidate.email == email)
        )
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        candidate = await self.get_by_email(email)
        return candidate is not None

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[Candidate]:
        result = await self.session.execute(
            select(Candidate).where(Candidate.id == entity_id)
        )
        return result.scalar_one_or_none()
