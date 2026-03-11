from __future__ import annotations

from src.config.openai_client import chat_json
from src.schemas.interview import EvaluationResponse
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

SYSTEM_PROMPT = """You are an expert interview evaluator.
Objectively evaluate a candidate's answer on a scale of 0-10 based on:
- Accuracy and correctness
- Depth of understanding
- Clarity of explanation
- Practical applicability
- Problem-solving approach

Return ONLY valid JSON:
{
  "score": <float 0-10>,
  "feedback": "<constructive feedback>",
  "strengths": ["<strength 1>"],
  "weaknesses": ["<weakness 1>"]
}"""


async def evaluate_answer(
    question_text: str,
    candidate_answer: str,
    question_skill: str,
    question_difficulty: str,
    jd_context: dict | None = None,
) -> EvaluationResponse:
    """Evaluate a candidate's answer using OpenAI."""

    difficulty_rubric = {
        "easy": "Basic understanding expected. Full marks for correct fundamentals.",
        "intermediate": "Solid understanding with practical examples expected.",
        "hard": "Deep expertise with edge cases and advanced concepts expected.",
    }
    rubric = difficulty_rubric.get(question_difficulty.lower(), difficulty_rubric["intermediate"])

    role_context = ""
    if jd_context:
        role_context = (
            f"\nROLE CONTEXT: Evaluating for {jd_context.get('job_title', '')} | "
            f"Required skills: {', '.join(jd_context.get('required_skills', []))}"
        )

    user_prompt = f"""Evaluate this interview response:

QUESTION: {question_text}
CANDIDATE'S ANSWER: {candidate_answer}
SKILL AREA: {question_skill}
DIFFICULTY: {question_difficulty}
RUBRIC: {rubric}{role_context}

Return ONLY the JSON object."""

    logger.debug("Evaluating answer | skill={} difficulty={}", question_skill, question_difficulty)

    try:
        data = await chat_json(SYSTEM_PROMPT, user_prompt)
        score = max(0.0, min(10.0, float(data.get("score", 5.0))))
        evaluation = EvaluationResponse(
            score=score,
            feedback=data.get("feedback", ""),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
        )
        logger.info("Evaluation complete | score={}", score)
        return evaluation
    except Exception as exc:
        logger.error("Evaluation error: {}", exc)
        raise ExternalServiceError(f"Failed to evaluate answer: {exc}") from exc
