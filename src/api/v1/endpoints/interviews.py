from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.deps import DbSession, RedisClient
from src.schemas.interview import (
    AnswerResponse,
    AnswerSubmit,
    InterviewStart,
    InterviewStartResponse,
    InterviewStatusResponse,
)
from src.services.interview import InterviewService
from src.utils import response as resp

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", status_code=201)
async def start_interview(
    body: InterviewStart,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    """Start an interview for a given session and generate the first question."""
    svc = InterviewService(db, redis)
    result = await svc.start_interview(body)
    return resp.created(
        data=result.model_dump(mode="json"),
        message=result.message,
    )


@router.post("/{session_id}/answer")
async def submit_answer(
    session_id: uuid.UUID,
    body: AnswerSubmit,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    """Submit an answer to the current question, get evaluation and next question."""
    svc = InterviewService(db, redis)
    result = await svc.submit_answer(session_id, body.answer, body.question_id)
    return resp.success(
        data=result.model_dump(mode="json"),
        message=result.message,
    )


@router.get("/{session_id}/status")
async def get_interview_status(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    """Get current interview state and last question."""
    svc = InterviewService(db, redis)
    status = await svc.get_interview_status(session_id)
    return resp.success(data=status.model_dump(mode="json"))


@router.post("/{session_id}/end")
async def end_interview(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    """Force-end an interview and trigger report generation."""
    svc = InterviewService(db, redis)
    await svc.force_end_interview(session_id)
    return resp.success(message="Interview ended and report generation triggered")
