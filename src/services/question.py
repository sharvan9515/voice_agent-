from __future__ import annotations

import uuid

from src.config.openai_client import chat_json
from src.schemas.interview import QuestionResponse
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

SYSTEM_PROMPT = """You are an expert interviewer conducting a professional interview.
Ask insightful, relevant questions that accurately assess the candidate's skills.
Be professional, encouraging, and neutral in tone.

Return ONLY valid JSON:
{
  "question_id": "<unique string id>",
  "skill": "<skill area being tested>",
  "difficulty": "<easy|intermediate|hard>",
  "text": "<the interview question>"
}"""


async def generate_question(
    skill: str,
    difficulty: str,
    conversation_history: list[dict],
    questions_asked: int = 0,
    jd_context: dict | None = None,
) -> QuestionResponse:
    """Generate the next interview question using OpenAI."""

    context_block = ""
    if jd_context:
        context_block = f"""
INTERVIEW CONTEXT:
- Role: {jd_context.get('job_title', skill)}
- Domain: {jd_context.get('domain', '')}
- Seniority: {jd_context.get('seniority_level', '')}
- Required skills: {', '.join(jd_context.get('required_skills', []))}
- Candidate skills: {', '.join(jd_context.get('candidate_skills', []))}
- Skill gaps to probe: {', '.join(jd_context.get('skill_gaps', []))}
- Candidate experience: {jd_context.get('candidate_experience_years', '')} years
Focus on probing skill gaps and verifying claimed skills.
"""

    recent = conversation_history[-6:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent
    ) if recent else "No previous conversation."

    user_prompt = f"""Generate interview question #{questions_asked + 1}.
- Skill area: {skill}
- Difficulty: {difficulty}
- Questions asked so far: {questions_asked}
{context_block}
Recent conversation:
{history_text}

Generate a NEW unique question not already asked. Return ONLY the JSON object."""

    logger.debug("Generating question | skill={} difficulty={} q_num={}", skill, difficulty, questions_asked + 1)

    try:
        data = await chat_json(SYSTEM_PROMPT, user_prompt)
        question = QuestionResponse(
            question_id=data.get("question_id", str(uuid.uuid4())),
            skill=data.get("skill", skill),
            difficulty=data.get("difficulty", difficulty),
            text=data["text"],
        )
        logger.info("Question generated | question_id={}", question.question_id)
        return question
    except Exception as exc:
        logger.error("Question generation error: {}", exc)
        raise ExternalServiceError(f"Failed to generate question: {exc}") from exc
