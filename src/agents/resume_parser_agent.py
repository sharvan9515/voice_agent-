"""ResumeParserAgent — parses resume text via LangChain chain with regex email pre-pass."""
from __future__ import annotations

import re
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.utils.logger import logger

# Regex for quick email extraction before LLM call
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


# --- Sub-models required by OpenAI structured output (no bare dicts) ---

class ExperienceEntry(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""


class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class ProjectEntry(BaseModel):
    name: str = ""
    description: str = ""
    tech_stack: List[str] = Field(default_factory=list)


class ParsedResumeOutput(BaseModel):
    """Structured output for resume parsing."""
    name: Optional[str] = None
    email: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    total_experience_years: float = 0.0
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are an expert recruiter. Extract structured information from resumes.
Extract name, email, skills, experience, education, projects, and certifications."""

HUMAN_TEMPLATE = """Parse this resume:

{raw_text}"""


class ResumeParserAgent(BaseAgent):
    name = "resume_parser"

    def build_chain(self) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=1024,
        ).with_structured_output(ParsedResumeOutput)

        chain = (
            RunnableLambda(lambda ctx: {"raw_text": ctx.get("raw_text", "")})
            | prompt
            | llm
            | RunnableLambda(lambda out: out.model_dump() if isinstance(out, ParsedResumeOutput) else out)
        )
        return chain

    async def run(self, ctx: dict) -> dict:
        """Parse resume with regex email pre-pass + LLM extraction."""
        raw_text = ctx.get("raw_text", "")
        logger.debug("ResumeParserAgent | text_length={}", len(raw_text))

        # Quick regex email extraction
        regex_email = None
        match = EMAIL_RE.search(raw_text)
        if match:
            regex_email = match.group(0)

        # Run LLM chain
        result = await self.build_chain().ainvoke(ctx)

        # Fill email from regex if LLM missed it
        if not result.get("email") and regex_email:
            result["email"] = regex_email

        logger.info("ResumeParserAgent complete | name={} skills={}",
                     result.get("name"), len(result.get("skills", [])))
        return result
