from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.candidate import Candidate
    from src.models.conversation_log import ConversationLog
    from src.models.interview_record import InterviewRecord
    from src.models.interview_report import InterviewReport
    from src.models.job import Job


class SessionStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        String(20),
        default=SessionStatus.INITIALIZED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="sessions")
    job: Mapped[Optional[Job]] = relationship("Job", back_populates="interview_sessions")
    conversation_logs: Mapped[list[ConversationLog]] = relationship(
        "ConversationLog", back_populates="session", cascade="all, delete-orphan"
    )
    interview_records: Mapped[list[InterviewRecord]] = relationship(
        "InterviewRecord", back_populates="session", cascade="all, delete-orphan"
    )
    report: Mapped[Optional[InterviewReport]] = relationship(
        "InterviewReport", back_populates="session", uselist=False
    )
