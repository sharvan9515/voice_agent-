from __future__ import annotations

import json
import re

from src.config.settings import settings
from src.schemas.job import ParsedJD
from src.services.question import get_anthropic_client
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

SYSTEM_PROMPT = """You are an expert HR analyst. Extract structured information from job descriptions.
Return ONLY valid JSON in this exact format:
{
  "title": "job title",
  "company": "company name or null",
  "required_skills": ["Python", "FastAPI"],
  "nice_to_have": ["Docker", "Kubernetes"],
  "responsibilities": ["Build REST APIs", "Design databases"],
  "min_experience_years": 3,
  "seniority_level": "mid",
  "domain": "backend engineering"
}
Do not include any text outside the JSON."""


async def parse_jd(raw_text: str) -> ParsedJD:
    client = get_anthropic_client()
    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Parse this job description:\n\n{raw_text}"}],
        )
        content = response.content[0].text.strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ExternalServiceError("Claude returned invalid JSON for JD parsing")
        return ParsedJD(**data)
    except ExternalServiceError:
        raise
    except Exception as exc:
        logger.error("JD parsing error: {}", exc)
        raise ExternalServiceError(f"JD parsing failed: {exc}") from exc
