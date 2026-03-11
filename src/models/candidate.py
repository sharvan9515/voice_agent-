from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.interview_session import InterviewSession
    from src.models.interview_report import InterviewReport


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    experience_level: Mapped[str] = mapped_column(String(50), nullable=False)
    skill_scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    resume_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_parsed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    sessions: Mapped[list[InterviewSession]] = relationship(
        "InterviewSession", back_populates="candidate", cascade="all, delete-orphan"
    )
    reports: Mapped[list[InterviewReport]] = relationship(
        "InterviewReport", back_populates="candidate", cascade="all, delete-orphan"
    )
