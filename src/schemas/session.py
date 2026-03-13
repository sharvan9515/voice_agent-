from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.interview_session import SessionStatus


class SessionCreate(BaseModel):
    candidate_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    started_at: datetime
    ended_at: Optional[datetime]
    total_score: Optional[float]
    status: SessionStatus
    created_at: datetime


class SessionState(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    questions_asked: int
    conversation_history: list[dict]
    current_question: Optional[dict]
    started_at: str
    jd_context: Optional[dict] = None
    resume_context: Optional[dict] = None
    interview_config: Optional[dict] = None
    topics_covered: list[str] = []
    follow_ups_this_topic: int = 0
    current_topic: str = ""
    interview_config: Optional[dict] = None
    topics_covered: list[str] = []
    follow_ups_this_topic: int = 0
    current_topic: str = ""
