"""JDParserAgent — parses job descriptions via LangChain chain."""
from __future__ import annotations

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.utils.logger import logger


class ParsedJDOutput(BaseModel):
    """Structured output for JD parsing."""
    title: str = ""
    company: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    min_experience_years: int = 0
    seniority_level: str = "mid"
    domain: str = "general"


SYSTEM_PROMPT = """You are an expert HR analyst. Extract structured information from job descriptions.
Extract title, company, required skills, nice-to-have skills, responsibilities, experience requirements, seniority level, and domain."""

HUMAN_TEMPLATE = """Parse this job description:

{raw_text}"""


class JDParserAgent(BaseAgent):
    name = "jd_parser"

    def build_chain(self) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=1024,
        ).with_structured_output(ParsedJDOutput)

        chain = (
            RunnableLambda(lambda ctx: {"raw_text": ctx.get("raw_text", "")})
            | prompt
            | llm
            | RunnableLambda(lambda out: out.model_dump() if isinstance(out, ParsedJDOutput) else out)
        )
        return chain

    async def run(self, ctx: dict) -> dict:
        logger.debug("JDParserAgent | text_length={}", len(ctx.get("raw_text", "")))
        result = await self.build_chain().ainvoke(ctx)
        logger.info("JDParserAgent complete | title={} skills={}",
                     result.get("title"), len(result.get("required_skills", [])))
        return result
