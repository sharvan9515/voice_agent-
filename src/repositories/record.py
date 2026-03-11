from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.interview_record import InterviewRecord
from src.repositories.base import BaseRepository


class RecordRepository(BaseRepository[InterviewRecord]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InterviewRecord, session)

    async def get_by_session(self, session_id: uuid.UUID) -> List[InterviewRecord]:
        result = await self.session.execute(
            select(InterviewRecord)
            .where(InterviewRecord.session_id == session_id)
            .order_by(InterviewRecord.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_by_session_with_evaluations(self, session_id: uuid.UUID) -> List[InterviewRecord]:
        result = await self.session.execute(
            select(InterviewRecord)
            .options(selectinload(InterviewRecord.evaluation))
            .where(InterviewRecord.session_id == session_id)
            .order_by(InterviewRecord.timestamp.asc())
        )
        return list(result.scalars().all())

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        records = await self.get_by_session(session_id)
        return len(records)
