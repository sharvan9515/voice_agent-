from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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
