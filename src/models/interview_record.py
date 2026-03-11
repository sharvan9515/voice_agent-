from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.interview_session import InterviewSession
    from src.models.evaluation_result import EvaluationResult


class InterviewRecord(Base):
    __tablename__ = "interview_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_skill: Mapped[str] = mapped_column(String(100), nullable=False)
    question_difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    candidate_answer: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    session: Mapped[InterviewSession] = relationship(
        "InterviewSession", back_populates="interview_records"
    )
    evaluation: Mapped[Optional[EvaluationResult]] = relationship(
        "EvaluationResult", back_populates="record", uselist=False
    )
