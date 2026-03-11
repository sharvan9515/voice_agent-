from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CandidateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    experience_level: str = Field(..., pattern="^(junior|mid|senior|lead|principal)$")
    skill_scores: Dict[str, Any] = Field(default_factory=dict)


class CandidateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    experience_level: str | None = Field(None, pattern="^(junior|mid|senior|lead|principal)$")
    skill_scores: Dict[str, Any] | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    experience_level: str
    skill_scores: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
