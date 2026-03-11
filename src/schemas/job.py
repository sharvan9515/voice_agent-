from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ParsedJD(BaseModel):
    title: str
    company: Optional[str] = None
    required_skills: list[str] = []
    nice_to_have: list[str] = []
    responsibilities: list[str] = []
    min_experience_years: int = 0
    seniority_level: str = "mid"  # junior/mid/senior
    domain: str = "general"


class JobCreate(BaseModel):
    title: str
    company: Optional[str] = None
    description_raw: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    company: Optional[str]
    description_raw: str
    description_parsed: dict
    created_at: datetime
