from __future__ import annotations

import json
import re
from typing import Optional

import anthropic

from src.config.settings import settings
from src.schemas.interview import EvaluationResponse
from src.services.question import get_anthropic_client
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

EVALUATOR_SYSTEM_PROMPT = """You are an expert technical interview evaluator.
Your task is to objectively evaluate a candidate's answer to an interview question.
Score the answer on a scale of 0-10 based on:
- Technical accuracy and correctness
- Depth of understanding
- Clarity of explanation
- Practical applicability
- Problem-solving approach

You MUST respond with ONLY valid JSON in the following format:
{
  "score": <float 0-10>,
  "feedback": "<constructive feedback paragraph>",
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "weaknesses": ["<weakness 1>", "<weakness 2>", ...]
}

Do not include any text outside the JSON object."""


async def evaluate_answer(
    question_text: str,
    candidate_answer: str,
    question_skill: str,
    question_difficulty: str,
    jd_context: dict | None = None,
) -> EvaluationResponse:
    """Evaluate a candidate's answer using Claude."""
    client = get_anthropic_client()

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

    user_prompt = f"""Evaluate the following interview response:

QUESTION: {question_text}

CANDIDATE'S ANSWER: {candidate_answer}

SKILL AREA: {question_skill}
DIFFICULTY LEVEL: {question_difficulty}
SCORING RUBRIC: {rubric}{role_context}

Provide an objective evaluation with a score from 0-10, constructive feedback, and lists of strengths and weaknesses.
Return ONLY the JSON object."""

    logger.debug(
        "Evaluating answer | skill={skill} | difficulty={difficulty}",
        skill=question_skill,
        difficulty=question_difficulty,
    )

    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=settings.CLAUDE_MAX_TOKENS,
            system=EVALUATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text.strip()

        try:
            eval_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                eval_data = json.loads(json_match.group())
            else:
                raise ExternalServiceError("Claude returned invalid JSON for evaluation")

        # Clamp score between 0 and 10
        score = float(eval_data.get("score", 5.0))
        score = max(0.0, min(10.0, score))

        evaluation = EvaluationResponse(
            score=score,
            feedback=eval_data.get("feedback", ""),
            strengths=eval_data.get("strengths", []),
            weaknesses=eval_data.get("weaknesses", []),
        )
        logger.info("Evaluation complete | score={score}", score=score)
        return evaluation

    except ExternalServiceError:
        raise
    except Exception as exc:
        logger.error("Evaluation error: {error}", error=str(exc))
        raise ExternalServiceError(f"Failed to evaluate answer: {exc}") from exc
