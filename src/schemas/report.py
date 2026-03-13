from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class QAEvaluation(BaseModel):
    score: float
    feedback: str
    evaluation_reasoning: str = ""
    metrics_used: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []


class QADetail(BaseModel):
    index: int
    question: str
    skill: str = ""
    difficulty: str = ""
    answer: str
    evaluation: Optional[QAEvaluation] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    candidate_id: uuid.UUID
    total_score: float
    strengths: List[str]
    weaknesses: List[str]
    summary: str
    export_url: Optional[str]
    qa_details: Optional[List[dict]] = None
    created_at: datetime


class ReportExport(BaseModel):
    report_id: uuid.UUID
    session_id: uuid.UUID
    candidate_id: uuid.UUID
    total_score: float
    strengths: List[str]
    weaknesses: List[str]
    summary: str
    records: List[dict]
    created_at: str
    exported_at: str
