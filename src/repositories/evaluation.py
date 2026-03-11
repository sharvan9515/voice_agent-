from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.evaluation_result import EvaluationResult
from src.repositories.base import BaseRepository


class EvaluationRepository(BaseRepository[EvaluationResult]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EvaluationResult, session)

    async def get_by_record_id(self, record_id: uuid.UUID) -> Optional[EvaluationResult]:
        result = await self.session.execute(
            select(EvaluationResult).where(EvaluationResult.record_id == record_id)
        )
        return result.scalar_one_or_none()
