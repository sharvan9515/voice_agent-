from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.conversation_log import ConversationLog
from src.models.evaluation_result import EvaluationResult
from src.models.interview_record import InterviewRecord
from src.models.interview_session import SessionStatus
from src.repositories.evaluation import EvaluationRepository
from src.repositories.record import RecordRepository
from src.repositories.session import SessionRepository
from src.schemas.interview import (
    AnswerResponse,
    EvaluationResponse,
    InterviewStart,
    InterviewStartResponse,
    InterviewStatusResponse,
    QuestionResponse,
)
from src.schemas.session import SessionState
from src.services import report as report_service_module
from src.services.evaluator import evaluate_answer
from src.services.question import generate_question
from src.services.session import SessionService
from src.utils.errors import NotFoundError, ValidationError
from src.utils.logger import logger


class InterviewService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.session_svc = SessionService(db, redis)
        self.record_repo = RecordRepository(db)
        self.eval_repo = EvaluationRepository(db)
        self.session_repo = SessionRepository(db)

    async def start_interview(self, data: InterviewStart) -> InterviewStartResponse:
        logger.info(
            "Starting interview | session_id={sid} | skill={skill}",
            sid=data.session_id,
            skill=data.skill,
        )

        session = await self.session_svc.get_session(data.session_id)
        if session.status not in (SessionStatus.INITIALIZED,):
            raise ValidationError(
                f"Session is already in status '{session.status.value}', cannot start interview"
            )

        # Update session status
        session.status = SessionStatus.IN_PROGRESS
        await self.session_repo.update(session)

        # Update Redis state
        state = await self.session_svc.get_session_state(data.session_id)
        state.status = SessionStatus.IN_PROGRESS.value

        # Generate first question
        first_question = await generate_question(
            skill=data.skill or settings.INTERVIEW_DEFAULT_SKILL,
            difficulty=data.difficulty or settings.INTERVIEW_DEFAULT_DIFFICULTY,
            conversation_history=state.conversation_history,
            questions_asked=0,
            jd_context=state.jd_context,
        )

        # Update state with first question
        state.current_question = first_question.model_dump()
        state.conversation_history.append(
            {
                "role": "agent",
                "content": first_question.text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self.session_svc.update_session_state(state)

        # Log to conversation_logs table
        log = ConversationLog(
            session_id=data.session_id,
            role="agent",
            content=first_question.text,
        )
        self.db.add(log)
        await self.db.flush()

        return InterviewStartResponse(
            session_id=data.session_id,
            first_question=first_question,
            message="Interview started successfully",
        )

    async def submit_answer(
        self, session_id: uuid.UUID, answer: str, question_id: str
    ) -> AnswerResponse:
        logger.info("Processing answer | session_id={sid}", sid=session_id)

        state = await self.session_svc.get_session_state(session_id)
        session = await self.session_svc.get_session(session_id)

        if session.status != SessionStatus.IN_PROGRESS:
            raise ValidationError("Interview is not in progress")

        current_q = state.current_question
        if not current_q:
            raise ValidationError("No active question found for this session")

        # Log candidate answer to conversation
        state.conversation_history.append(
            {
                "role": "candidate",
                "content": answer,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Persist conversation log
        candidate_log = ConversationLog(
            session_id=session_id,
            role="candidate",
            content=answer,
        )
        self.db.add(candidate_log)

        # Evaluate the answer
        evaluation = await evaluate_answer(
            question_text=current_q["text"],
            candidate_answer=answer,
            question_skill=current_q["skill"],
            question_difficulty=current_q["difficulty"],
            jd_context=state.jd_context,
        )

        # Persist InterviewRecord
        record = InterviewRecord(
            session_id=session_id,
            question_id=current_q["question_id"],
            question_text=current_q["text"],
            question_skill=current_q["skill"],
            question_difficulty=current_q["difficulty"],
            candidate_answer=answer,
        )
        record = await self.record_repo.create(record)

        # Persist EvaluationResult
        eval_result = EvaluationResult(
            record_id=record.id,
            score=evaluation.score,
            feedback=evaluation.feedback,
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
        )
        self.db.add(eval_result)
        await self.db.flush()

        # Increment questions asked
        state.questions_asked += 1
        max_q = settings.INTERVIEW_MAX_QUESTIONS

        interview_complete = state.questions_asked >= max_q
        next_question: Optional[QuestionResponse] = None

        if not interview_complete:
            # Generate next question
            next_question = await generate_question(
                skill=current_q["skill"],
                difficulty=current_q["difficulty"],
                conversation_history=state.conversation_history,
                questions_asked=state.questions_asked,
                jd_context=state.jd_context,
            )

            state.current_question = next_question.model_dump()
            state.conversation_history.append(
                {
                    "role": "agent",
                    "content": next_question.text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Log agent question
            agent_log = ConversationLog(
                session_id=session_id,
                role="agent",
                content=next_question.text,
            )
            self.db.add(agent_log)
        else:
            state.status = SessionStatus.COMPLETED.value
            state.current_question = None

        await self.session_svc.update_session_state(state)

        if interview_complete:
            # Trigger report generation asynchronously
            await self._finalize_interview(session_id)

        message = (
            "Interview completed! Your report is being generated."
            if interview_complete
            else f"Answer recorded. Question {state.questions_asked + 1} of {max_q}."
        )

        return AnswerResponse(
            evaluation=evaluation,
            next_question=next_question,
            interview_complete=interview_complete,
            message=message,
        )

    async def _finalize_interview(self, session_id: uuid.UUID) -> None:
        from src.services.report import ReportService

        report_svc = ReportService(self.db)

        # Get all records with evaluations to compute average score
        records = await self.record_repo.get_by_session_with_evaluations(session_id)
        scores = [r.evaluation.score for r in records if r.evaluation]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        session = await self.session_svc.get_session(session_id)
        await self.session_svc.end_session(session_id, total_score=avg_score)

        try:
            await report_svc.generate_report(session_id)
        except Exception as exc:
            logger.error("Failed to auto-generate report: {err}", err=str(exc))

    async def get_interview_status(self, session_id: uuid.UUID) -> InterviewStatusResponse:
        state = await self.session_svc.get_session_state(session_id)
        session = await self.session_svc.get_session(session_id)

        current_q: Optional[QuestionResponse] = None
        if state.current_question:
            current_q = QuestionResponse(**state.current_question)

        return InterviewStatusResponse(
            session_id=session_id,
            status=session.status.value,
            questions_asked=state.questions_asked,
            max_questions=settings.INTERVIEW_MAX_QUESTIONS,
            current_question=current_q,
            last_evaluation=None,
        )

    async def force_end_interview(self, session_id: uuid.UUID) -> None:
        logger.info("Force ending interview | session_id={sid}", sid=session_id)
        session = await self.session_svc.get_session(session_id)

        records = await self.record_repo.get_by_session_with_evaluations(session_id)
        scores = [r.evaluation.score for r in records if r.evaluation]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        await self.session_svc.end_session(session_id, total_score=avg_score)

        from src.services.report import ReportService
        report_svc = ReportService(self.db)
        try:
            await report_svc.generate_report(session_id)
        except Exception as exc:
            logger.error("Failed to generate report on force-end: {err}", err=str(exc))
