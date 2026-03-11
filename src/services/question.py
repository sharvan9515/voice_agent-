from __future__ import annotations

import json
import uuid
from typing import Optional

import anthropic

from src.config.settings import settings
from src.schemas.interview import QuestionResponse
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


SYSTEM_PROMPT = """You are an expert technical interviewer conducting a professional voice-based interview.
Your role is to ask insightful, relevant questions that accurately assess the candidate's skills and experience.
You must be professional, encouraging, and neutral in tone.

When generating a question, you MUST respond with ONLY valid JSON in the following format:
{
  "question_id": "<unique string id>",
  "skill": "<skill area being tested>",
  "difficulty": "<easy|intermediate|hard>",
  "text": "<the interview question text>"
}

Do not include any text outside the JSON object."""


async def generate_question(
    skill: str,
    difficulty: str,
    conversation_history: list[dict],
    questions_asked: int = 0,
    jd_context: dict | None = None,
) -> QuestionResponse:
    """Generate the next interview question using Claude."""
    client = get_anthropic_client()

    # Build context from last 6 conversation turns
    history_context = ""
    recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
    if recent_history:
        history_lines = []
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            history_lines.append(f"{role.upper()}: {content}")
        history_context = "\n".join(history_lines)

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

Focus questions on probing skill gaps and verifying claimed skills.
"""

    user_prompt = f"""Generate interview question #{questions_asked + 1} for the following context:
- Skill area: {skill}
- Difficulty level: {difficulty}
- Questions asked so far: {questions_asked}
{context_block}
Recent conversation history:
{history_context if history_context else "No previous conversation."}

Generate a new, unique question that has NOT been asked before based on the conversation history.
The question should progressively build on previous topics if applicable.
Return ONLY the JSON object."""

    logger.debug(
        "Generating question | skill={skill} | difficulty={difficulty} | q_num={num}",
        skill=skill,
        difficulty=difficulty,
        num=questions_asked + 1,
    )

    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text.strip()

        # Parse JSON response
        try:
            question_data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                question_data = json.loads(json_match.group())
            else:
                raise ExternalServiceError("Claude returned invalid JSON for question generation")

        question = QuestionResponse(
            question_id=question_data.get("question_id", str(uuid.uuid4())),
            skill=question_data.get("skill", skill),
            difficulty=question_data.get("difficulty", difficulty),
            text=question_data["text"],
        )
        logger.info("Question generated | question_id={qid}", qid=question.question_id)
        return question

    except ExternalServiceError:
        raise
    except Exception as exc:
        logger.error("Question generation error: {error}", error=str(exc))
        raise ExternalServiceError(f"Failed to generate interview question: {exc}") from exc
