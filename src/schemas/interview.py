from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class InterviewStart(BaseModel):
    session_id: uuid.UUID
    candidate_id: uuid.UUID
    skill: str = "general"
    difficulty: str = "intermediate"


class AnswerSubmit(BaseModel):
    answer: str = Field(..., min_length=1)
    question_id: str


class QuestionResponse(BaseModel):
    question_id: str
    skill: str
    difficulty: str
    text: str


class EvaluationResponse(BaseModel):
    score: float
    feedback: str
    strengths: List[str]
    weaknesses: List[str]


class InterviewStatusResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    questions_asked: int
    max_questions: int
    current_question: Optional[QuestionResponse]
    last_evaluation: Optional[EvaluationResponse]


class AnswerResponse(BaseModel):
    evaluation: EvaluationResponse
    next_question: Optional[QuestionResponse]
    interview_complete: bool
    message: str


class InterviewStartResponse(BaseModel):
    session_id: uuid.UUID
    first_question: QuestionResponse
    message: str


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    question_id: str
    question_text: str
    question_skill: str
    question_difficulty: str
    candidate_answer: str
    timestamp: datetime
