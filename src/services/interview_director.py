"""
Interview Director Service
--------------------------
LLM-driven orchestrator that decides the next interview action based on
conversation history, the candidate's latest answer, and the JD/resume context.

Actions:
  follow_up     — candidate answer was vague/incomplete, probe deeper
  next_question — answer was sufficient, move to next topic
  end_interview — all key topics covered OR max questions reached
"""
from __future__ import annotations

import uuid

from src.config.openai_client import chat_json
from src.config.settings import settings
from src.schemas.session import SessionState
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

DIRECTOR_SYSTEM_PROMPT = """You are an expert interview director conducting a professional, domain-agnostic interview.

Your job is to decide the next action after a candidate answers:
1. "follow_up"     — the answer was incomplete, vague, or needs clarification; ask a targeted follow-up
2. "next_question" — the answer was satisfactory; move to a new topic or skill area
3. "end_interview" — all major topics have been covered OR the question count limit is reached

Rules:
- Be adaptive: adjust question depth based on the answer quality
- Never repeat a question already asked
- Stay within the domain and seniority level of the role
- If max_questions is reached, always return "end_interview"

Return ONLY valid JSON (no markdown, no explanation):
{
  "action": "follow_up" | "next_question" | "end_interview",
  "question_text": "<the follow-up or new question; empty string if end_interview>",
  "topic": "<skill/topic being tested>",
  "reasoning": "<one sentence internal reasoning>"
}"""


async def decide_next_action(
    state: SessionState,
    latest_transcript: str,
    max_questions: int = 10,
) -> dict:
    """
    Ask GPT-4o to decide the next interview action.

    Returns a dict with keys: action, question_text, topic, reasoning
    """
    context_block = _build_context_block(state)

    recent_history = state.conversation_history[-10:]
    history_text = (
        "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent_history)
        if recent_history
        else "No previous conversation yet."
    )

    force_end = state.questions_asked >= max_questions
    end_note = (
        "\nNOTE: The question limit has been reached. You MUST return action='end_interview'."
        if force_end
        else ""
    )

    user_prompt = f"""CONVERSATION SO FAR:
{history_text}

CANDIDATE'S LATEST ANSWER:
{latest_transcript}

PROGRESS: {state.questions_asked} question(s) asked. Max allowed: {max_questions}.{end_note}
{context_block}

Decide the next action and return ONLY the JSON object."""

    logger.debug(
        "Interview director called | session={} | q_asked={} | force_end={}",
        state.session_id,
        state.questions_asked,
        force_end,
    )

    try:
        data = await chat_json(DIRECTOR_SYSTEM_PROMPT, user_prompt, max_tokens=512)
        action = data.get("action", "next_question")
        # Enforce max questions
        if force_end:
            action = "end_interview"

        result = {
            "action": action,
            "question_text": data.get("question_text", "") if action != "end_interview" else "",
            "topic": data.get("topic", "general"),
            "reasoning": data.get("reasoning", ""),
        }
        logger.info(
            "Director decision | session={} | action={} | topic={}",
            state.session_id,
            result["action"],
            result["topic"],
        )
        return result
    except Exception as exc:
        logger.error("Interview director error: {}", exc)
        raise ExternalServiceError(f"Interview director failed: {exc}") from exc


async def generate_opening_question(state: SessionState) -> dict:
    """Generate the very first question for the interview."""

    context_block = _build_context_block(state)

    user_prompt = f"""Generate the FIRST interview question for this candidate.
{context_block}

Start with a warm opening question that assesses the candidate's background
relevant to the role. Return ONLY the JSON:
{{
  "action": "next_question",
  "question_text": "<opening question>",
  "topic": "<topic>",
  "reasoning": "opening question"
}}"""

    try:
        data = await chat_json(DIRECTOR_SYSTEM_PROMPT, user_prompt, max_tokens=256)
        return {
            "action": "next_question",
            "question_text": data.get("question_text", "Tell me about yourself and your relevant experience."),
            "topic": data.get("topic", "background"),
            "reasoning": "opening question",
        }
    except Exception as exc:
        logger.error("Opening question generation error: {}", exc)
        raise ExternalServiceError(f"Failed to generate opening question: {exc}") from exc


def _build_context_block(state: SessionState) -> str:
    """Build the JD + resume context string for prompts."""
    if not state.jd_context:
        return ""

    jd = state.jd_context
    lines = [
        "\nINTERVIEW CONTEXT:",
        f"- Role: {jd.get('job_title', 'Professional')}",
        f"- Domain: {jd.get('domain', '')}",
        f"- Seniority: {jd.get('seniority_level', '')}",
        f"- Required skills to assess: {', '.join(jd.get('required_skills', []))}",
        f"- Candidate's claimed skills: {', '.join(jd.get('candidate_skills', []))}",
        f"- Skill gaps to probe: {', '.join(jd.get('skill_gaps', []))}",
        f"- Candidate experience: {jd.get('candidate_experience_years', 'unknown')} years",
    ]
    return "\n".join(lines)
