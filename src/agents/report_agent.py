"""ReportAgent — narrative report generation via LangChain chain."""
from __future__ import annotations

import json
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.utils.logger import logger


class ReportOutput(BaseModel):
    """Structured output for interview report narrative."""
    summary: str = Field(description="Detailed narrative summary paragraph")
    overall_strengths: List[str] = Field(default_factory=list)
    overall_weaknesses: List[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are an expert technical interview assessor writing a comprehensive candidate evaluation report.
Based on the interview data provided, generate a professional narrative summary."""

HUMAN_TEMPLATE = """Generate a comprehensive evaluation report for a candidate interview.

OVERALL SCORE: {total_score}/10

INTERVIEW TRANSCRIPT SUMMARY:
{interview_summary}

OBSERVED STRENGTHS: {strengths}
OBSERVED WEAKNESSES: {weaknesses}

Write a professional narrative summary and refine the strengths/weaknesses lists."""


class ReportAgent(BaseAgent):
    name = "report"

    def build_chain(self) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=1024,
        ).with_structured_output(ReportOutput)

        def _prepare(ctx: dict) -> dict:
            return {
                "total_score": f"{ctx.get('total_score', 0.0):.1f}",
                "interview_summary": ctx.get("interview_summary", ""),
                "strengths": json.dumps(ctx.get("strengths", [])),
                "weaknesses": json.dumps(ctx.get("weaknesses", [])),
            }

        chain = (
            RunnableLambda(_prepare)
            | prompt
            | llm
            | RunnableLambda(lambda out: out.model_dump() if isinstance(out, ReportOutput) else out)
        )
        return chain

    async def run(self, ctx: dict) -> dict:
        logger.debug("ReportAgent | score={}", ctx.get("total_score"))
        try:
            result = await self.build_chain().ainvoke(ctx)
            logger.info("ReportAgent complete")
            return result
        except Exception as exc:
            logger.error("ReportAgent narrative generation error: {}", str(exc))
            return {
                "summary": (
                    f"The candidate completed the interview with an overall score of "
                    f"{ctx.get('total_score', 0.0):.1f}/10. "
                    f"They demonstrated competency in several areas while having room for improvement in others."
                ),
                "overall_strengths": ctx.get("strengths", []),
                "overall_weaknesses": ctx.get("weaknesses", []),
            }
