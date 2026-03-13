"""QuestionAgent — generates interview questions via LangChain chain."""
from __future__ import annotations

import uuid
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.utils.logger import logger


class QuestionOutput(BaseModel):
    """Structured output for generated question."""
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill: str
    difficulty: str
    text: str


SYSTEM_PROMPT = """You are an expert interviewer conducting a professional interview.
Ask insightful, relevant questions that accurately assess the candidate's skills.
Be professional, encouraging, and neutral in tone."""

HUMAN_TEMPLATE = """Generate interview question #{question_number}.
- Skill area: {skill}
- Difficulty: {difficulty}
- Questions asked so far: {questions_asked}
{context_block}
Recent conversation:
{history_text}

Generate a NEW unique question not already asked."""


class QuestionAgent(BaseAgent):
    name = "question"

    def build_chain(self) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=512,
        ).with_structured_output(QuestionOutput)

        def _prepare(ctx: dict) -> dict:
            jd_context = ctx.get("jd_context") or {}
            context_block = ""
            if jd_context:
                context_block = (
                    f"\nINTERVIEW CONTEXT:\n"
                    f"- Role: {jd_context.get('job_title', ctx.get('skill', 'general'))}\n"
                    f"- Domain: {jd_context.get('domain', '')}\n"
                    f"- Seniority: {jd_context.get('seniority_level', '')}\n"
                    f"- Required skills: {', '.join(jd_context.get('required_skills', []))}\n"
                    f"- Candidate skills: {', '.join(jd_context.get('candidate_skills', []))}\n"
                    f"- Skill gaps to probe: {', '.join(jd_context.get('skill_gaps', []))}\n"
                    f"- Candidate experience: {jd_context.get('candidate_experience_years', '')} years\n"
                    f"Focus on probing skill gaps and verifying claimed skills."
                )

            history = ctx.get("conversation_history", [])[-6:]
            history_text = (
                "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
                if history else "No previous conversation."
            )

            questions_asked = ctx.get("questions_asked", 0)
            return {
                "question_number": questions_asked + 1,
                "skill": ctx.get("skill", settings.INTERVIEW_DEFAULT_SKILL),
                "difficulty": ctx.get("difficulty", settings.INTERVIEW_DEFAULT_DIFFICULTY),
                "questions_asked": questions_asked,
                "context_block": context_block,
                "history_text": history_text,
            }

        chain = RunnableLambda(_prepare) | prompt | llm | RunnableLambda(
            lambda out: out.model_dump() if isinstance(out, QuestionOutput) else out
        )
        return chain

    async def run(self, ctx: dict) -> dict:
        logger.debug("QuestionAgent | skill={} q_num={}",
                      ctx.get("skill"), ctx.get("questions_asked", 0) + 1)
        result = await self.build_chain().ainvoke(ctx)
        logger.info("QuestionAgent complete | question_id={}", result.get("question_id"))
        return result
