from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    transcript: str
    duration_seconds: Optional[float] = None
    language: Optional[str] = None


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: Optional[str] = None
    model_id: Optional[str] = None


class SynthesizeResponse(BaseModel):
    audio_url: Optional[str] = None
    content_type: str = "audio/mpeg"
    size_bytes: int
