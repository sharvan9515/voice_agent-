from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.interview_report import InterviewReport
from src.repositories.base import BaseRepository


class ReportRepository(BaseRepository[InterviewReport]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InterviewReport, session)

    async def get_by_session_id(self, session_id: uuid.UUID) -> Optional[InterviewReport]:
        result = await self.session.execute(
            select(InterviewReport).where(InterviewReport.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_candidate(self, candidate_id: uuid.UUID) -> list[InterviewReport]:
        result = await self.session.execute(
            select(InterviewReport)
            .where(InterviewReport.candidate_id == candidate_id)
            .order_by(InterviewReport.created_at.desc())
        )
        return list(result.scalars().all())
