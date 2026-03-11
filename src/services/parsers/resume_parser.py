from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.config.openai_client import chat_json
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger


class ParsedResume(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    skills: list[str] = []
    total_experience_years: float = 0.0
    experience: list[dict] = []
    education: list[dict] = []
    projects: list[dict] = []
    certifications: list[str] = []


SYSTEM_PROMPT = """You are an expert recruiter. Extract structured information from resumes.
Return ONLY valid JSON:
{
  "name": "John Doe",
  "email": "john@example.com",
  "skills": ["Python", "FastAPI"],
  "total_experience_years": 3.5,
  "experience": [{"title": "Engineer", "company": "Acme", "duration": "2 years", "description": "Built APIs"}],
  "education": [{"degree": "B.Tech CS", "institution": "IIT", "year": "2020"}],
  "projects": [{"name": "Project", "description": "Description", "tech_stack": ["Python"]}],
  "certifications": ["AWS Solutions Architect"]
}"""


async def parse_resume(raw_text: str) -> ParsedResume:
    """Parse resume text into structured ParsedResume using OpenAI."""
    logger.debug("Parsing resume | length={}", len(raw_text))
    try:
        data = await chat_json(SYSTEM_PROMPT, f"Parse this resume:\n\n{raw_text}", max_tokens=1024)
        return ParsedResume(**data)
    except Exception as exc:
        logger.error("Resume parsing error: {}", exc)
        raise ExternalServiceError(f"Resume parsing failed: {exc}") from exc
