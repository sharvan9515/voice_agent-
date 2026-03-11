from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel

from src.config.settings import settings
from src.services.question import get_anthropic_client
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger


class ParsedResume(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    skills: list[str] = []
    total_experience_years: float = 0.0
    experience: list[dict] = []   # [{title, company, duration, description}]
    education: list[dict] = []    # [{degree, institution, year}]
    projects: list[dict] = []     # [{name, description, tech_stack}]
    certifications: list[str] = []


SYSTEM_PROMPT = """You are an expert recruiter. Extract structured information from resumes.
Return ONLY valid JSON in this exact format:
{
  "name": "John Doe",
  "email": "john@example.com",
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "total_experience_years": 3.5,
  "experience": [{"title": "Backend Engineer", "company": "Acme", "duration": "2 years", "description": "Built APIs"}],
  "education": [{"degree": "B.Tech CS", "institution": "IIT", "year": "2020"}],
  "projects": [{"name": "Voice Agent", "description": "AI interview system", "tech_stack": ["Python", "FastAPI"]}],
  "certifications": ["AWS Solutions Architect"]
}
Do not include any text outside the JSON."""


async def parse_resume(raw_text: str) -> ParsedResume:
    client = get_anthropic_client()
    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Parse this resume:\n\n{raw_text}"}],
        )
        content = response.content[0].text.strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ExternalServiceError("Claude returned invalid JSON for resume parsing")
        return ParsedResume(**data)
    except ExternalServiceError:
        raise
    except Exception as exc:
        logger.error("Resume parsing error: {}", exc)
        raise ExternalServiceError(f"Resume parsing failed: {exc}") from exc
