"""EvaluatorAgent — scores candidate answers 0-10 via LangChain chain."""
from __future__ import annotations

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.utils.logger import logger


class EvaluationOutput(BaseModel):
    """Structured output for answer evaluation."""
    score: float = Field(ge=0, le=10, description="Score from 0 to 10")
    feedback: str = Field(description="Constructive feedback")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are an expert interview evaluator.
Objectively evaluate a candidate's answer on a scale of 0-10 based on:
- Accuracy and correctness
- Depth of understanding
- Clarity of explanation
- Practical applicability
- Problem-solving approach"""

HUMAN_TEMPLATE = """Evaluate this interview response:

QUESTION: {question_text}
CANDIDATE'S ANSWER: {candidate_answer}
SKILL AREA: {question_skill}
DIFFICULTY: {question_difficulty}
RUBRIC: {rubric}
{role_context}

Return your evaluation."""


DIFFICULTY_RUBRICS = {
    "easy": "Basic understanding expected. Full marks for correct fundamentals.",
    "intermediate": "Solid understanding with practical examples expected.",
    "hard": "Deep expertise with edge cases and advanced concepts expected.",
}


class EvaluatorAgent(BaseAgent):
    name = "evaluator"

    def build_chain(self) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=512,
        ).with_structured_output(EvaluationOutput)

        def _prepare(ctx: dict) -> dict:
            difficulty = ctx.get("question_difficulty", "intermediate").lower()
            rubric = DIFFICULTY_RUBRICS.get(difficulty, DIFFICULTY_RUBRICS["intermediate"])
            jd = ctx.get("jd_context") or {}
            role_context = ""
            if jd:
                role_context = (
                    f"ROLE CONTEXT: Evaluating for {jd.get('job_title', '')} | "
                    f"Required skills: {', '.join(jd.get('required_skills', []))}"
                )
            return {
                "question_text": ctx.get("question_text", ""),
                "candidate_answer": ctx.get("candidate_answer", ""),
                "question_skill": ctx.get("question_skill", "general"),
                "question_difficulty": difficulty,
                "rubric": rubric,
                "role_context": role_context,
            }

        chain = RunnableLambda(_prepare) | prompt | llm | RunnableLambda(
            lambda out: out.model_dump() if isinstance(out, EvaluationOutput) else out
        )
        return chain

    async def run(self, ctx: dict) -> dict:
        logger.debug("EvaluatorAgent | skill={} difficulty={}",
                      ctx.get("question_skill"), ctx.get("question_difficulty"))
        result = await self.build_chain().ainvoke(ctx)
        # Clamp score
        result["score"] = max(0.0, min(10.0, float(result.get("score", 5.0))))
        logger.info("EvaluatorAgent complete | score={}", result["score"])
        return result
