from __future__ import annotations

from src.config.openai_client import chat_json
from src.schemas.job import ParsedJD
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

SYSTEM_PROMPT = """You are an expert HR analyst. Extract structured information from job descriptions.
Return ONLY valid JSON:
{
  "title": "job title",
  "company": "company name or null",
  "required_skills": ["Python", "FastAPI"],
  "nice_to_have": ["Docker"],
  "responsibilities": ["Build REST APIs"],
  "min_experience_years": 3,
  "seniority_level": "mid",
  "domain": "backend engineering"
}"""


async def parse_jd(raw_text: str) -> ParsedJD:
    """Parse a raw JD string into structured ParsedJD using OpenAI."""
    logger.debug("Parsing JD | length={}", len(raw_text))
    try:
        data = await chat_json(SYSTEM_PROMPT, f"Parse this job description:\n\n{raw_text}", max_tokens=1024)
        return ParsedJD(**data)
    except Exception as exc:
        logger.error("JD parsing error: {}", exc)
        raise ExternalServiceError(f"JD parsing failed: {exc}") from exc
