from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.deps import DbSession, RedisClient
from src.schemas.session import SessionCreate, SessionResponse, SessionState
from src.services.session import SessionService
from src.utils import response as resp

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201)
async def create_session(body: SessionCreate, db: DbSession, redis: RedisClient) -> JSONResponse:
    """Create a new interview session."""
    svc = SessionService(db, redis)
    session = await svc.create_session(body)
    return resp.created(
        data=SessionResponse.model_validate(session).model_dump(mode="json"),
        message="Session created successfully",
    )


@router.get("/{session_id}")
async def get_session(session_id: uuid.UUID, db: DbSession, redis: RedisClient) -> JSONResponse:
    """Get current session state."""
    svc = SessionService(db, redis)
    state = await svc.get_session_state(session_id)
    return resp.success(data=state.model_dump())


@router.delete("/{session_id}")
async def end_session(session_id: uuid.UUID, db: DbSession, redis: RedisClient) -> JSONResponse:
    """End a session, flushing the Redis cache key."""
    svc = SessionService(db, redis)
    session = await svc.abort_session(session_id)
    return resp.success(
        data=SessionResponse.model_validate(session).model_dump(mode="json"),
        message="Session ended",
    )
