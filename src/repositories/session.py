from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.interview_session import InterviewSession, SessionStatus
from src.repositories.base import BaseRepository


class SessionRepository(BaseRepository[InterviewSession]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(InterviewSession, session)

    async def get_by_id_with_relations(self, session_id: uuid.UUID) -> Optional[InterviewSession]:
        result = await self.session.execute(
            select(InterviewSession)
            .options(
                selectinload(InterviewSession.candidate),
                selectinload(InterviewSession.conversation_logs),
                selectinload(InterviewSession.interview_records),
            )
            .where(InterviewSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_candidate(self, candidate_id: uuid.UUID) -> List[InterviewSession]:
        result = await self.session.execute(
            select(InterviewSession)
            .where(InterviewSession.candidate_id == candidate_id)
            .order_by(InterviewSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_sessions(self) -> List[InterviewSession]:
        result = await self.session.execute(
            select(InterviewSession).where(
                InterviewSession.status == SessionStatus.IN_PROGRESS
            )
        )
        return list(result.scalars().all())
