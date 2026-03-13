from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.interview_session import InterviewSession
    from src.models.candidate import Candidate


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    weaknesses: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    export_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # Per-question breakdown: list of {question, answer, skill, difficulty,
    # score, feedback, evaluation_reasoning, metrics_used, strengths, weaknesses}
    qa_details: Mapped[Optional[List[dict]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    session: Mapped[InterviewSession] = relationship(
        "InterviewSession", back_populates="report"
    )
    candidate: Mapped[Candidate] = relationship(
        "Candidate", back_populates="reports"
    )
