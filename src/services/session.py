from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.interview_session import InterviewSession, SessionStatus
from src.repositories.candidate import CandidateRepository
from src.repositories.job import JobRepository
from src.repositories.session import SessionRepository
from src.schemas.job import ParsedJD
from src.schemas.session import SessionCreate, SessionState
from src.services.parsers.context_builder import build_context
from src.services.parsers.resume_parser import ParsedResume
from src.utils.errors import NotFoundError
from src.utils.logger import logger

SESSION_KEY_PREFIX = "session:"


def _session_redis_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


class SessionService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.repo = SessionRepository(db)
        self.candidate_repo = CandidateRepository(db)

    async def create_session(self, data: SessionCreate) -> InterviewSession:
        logger.info("Creating session | candidate_id={cid}", cid=data.candidate_id)

        candidate = await self.candidate_repo.get_by_id(data.candidate_id)
        if not candidate:
            raise NotFoundError(f"Candidate '{data.candidate_id}' not found")

        session = InterviewSession(
            candidate_id=data.candidate_id,
            job_id=data.job_id,
            status=SessionStatus.INITIALIZED,
        )
        session = await self.repo.create(session)

        # Build JD/resume context if job_id is provided
        jd_context = None
        resume_context = None

        if data.job_id:
            job_repo = JobRepository(self.db)
            job = await job_repo.get_by_id(data.job_id)
            if job and job.description_parsed and candidate.resume_parsed:
                try:
                    jd = ParsedJD(**job.description_parsed)
                    resume = ParsedResume(**candidate.resume_parsed)
                    ctx = build_context(jd, resume)
                    jd_context = ctx.model_dump()
                    resume_context = {
                        "skills": resume.skills,
                        "experience_years": resume.total_experience_years,
                    }
                except Exception as e:
                    logger.warning("Could not build interview context: {}", e)

        # Cache initial state in Redis
        state = SessionState(
            session_id=str(session.id),
            candidate_id=str(session.candidate_id),
            status=SessionStatus.INITIALIZED.value,
            questions_asked=0,
            conversation_history=[],
            current_question=None,
            started_at=session.started_at.isoformat(),
            jd_context=jd_context,
            resume_context=resume_context,
        )
        await self.redis.setex(
            _session_redis_key(str(session.id)),
            settings.REDIS_SESSION_TTL_SECONDS,
            state.model_dump_json(),
        )
        logger.info("Session created | session_id={sid}", sid=session.id)
        return session

    async def get_session(self, session_id: uuid.UUID) -> InterviewSession:
        # Check Redis first — if not in cache, it may have expired or never existed
        cached = await self.redis.get(_session_redis_key(str(session_id)))
        # We still need the SQLAlchemy ORM object for relationships, fetch from DB
        session = await self.repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session '{session_id}' not found")
        return session

    async def get_session_state(self, session_id: uuid.UUID) -> SessionState:
        cached = await self.redis.get(_session_redis_key(str(session_id)))
        if cached:
            return SessionState.model_validate_json(cached)

        # Rebuild from DB
        session = await self.repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session '{session_id}' not found")

        state = SessionState(
            session_id=str(session.id),
            candidate_id=str(session.candidate_id),
            status=session.status.value,
            questions_asked=0,
            conversation_history=[],
            current_question=None,
            started_at=session.started_at.isoformat(),
        )
        return state

    async def update_session_state(self, state: SessionState) -> None:
        await self.redis.setex(
            _session_redis_key(state.session_id),
            settings.REDIS_SESSION_TTL_SECONDS,
            state.model_dump_json(),
        )

    async def append_message(
        self, session_id: uuid.UUID, role: str, content: str
    ) -> None:
        state = await self.get_session_state(session_id)
        state.conversation_history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self.update_session_state(state)

    async def end_session(
        self, session_id: uuid.UUID, total_score: Optional[float] = None
    ) -> InterviewSession:
        logger.info("Ending session | session_id={sid}", sid=session_id)
        session = await self.get_session(session_id)
        session.ended_at = datetime.now(timezone.utc)
        session.status = SessionStatus.COMPLETED
        if total_score is not None:
            session.total_score = total_score

        session = await self.repo.update(session)

        # Flush Redis key
        await self.redis.delete(_session_redis_key(str(session_id)))
        logger.info("Session ended | session_id={sid}", sid=session_id)
        return session

    async def abort_session(self, session_id: uuid.UUID) -> InterviewSession:
        logger.info("Aborting session | session_id={sid}", sid=session_id)
        session = await self.get_session(session_id)
        session.ended_at = datetime.now(timezone.utc)
        session.status = SessionStatus.ABORTED
        session = await self.repo.update(session)
        await self.redis.delete(_session_redis_key(str(session_id)))
        return session
