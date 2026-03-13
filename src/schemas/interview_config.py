from __future__ import annotations

from pydantic import BaseModel


class InterviewConfig(BaseModel):
    max_questions: int = 8
    max_follow_ups_per_topic: int = 2
    depth: str = "standard"          # surface | standard | deep
    style: str = "mixed"             # technical | behavioral | mixed
    focus_areas: list[str] = []      # [] = use JD skill gaps
    screen_threshold: int = 40       # fit score < this → skip interview
    tts_voice: str = "alloy"         # OpenAI TTS voice per session