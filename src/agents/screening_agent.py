"""ScreeningAgent — pure-math fit score, no LLM. Uses RunnableLambda."""
from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from src.agents.base import BaseAgent
from src.utils.logger import logger


class ScreeningResult(BaseModel):
    fit_score: float
    verdict: str  # "qualified" | "unqualified"
    matched_skills: list[str]
    missing_skills: list[str]
    experience_match: bool
    breakdown: dict


def _compute_fit_score(ctx: dict) -> dict:
    """
    fit_score = (skills_match * 50) + (experience_ratio * 30) + (domain_match * 20)

    ctx must contain:
      - required_skills: list[str]
      - candidate_skills: list[str]
      - required_experience_years: int
      - candidate_experience_years: float
      - jd_domain: str
      - candidate_domain: str  (optional, defaults to "")
      - threshold: int (default 40)
    """
    required = {s.lower() for s in ctx.get("required_skills", [])}
    candidate = {s.lower() for s in ctx.get("candidate_skills", [])}

    matched = sorted(required & candidate)
    missing = sorted(required - candidate)
    skills_ratio = len(matched) / len(required) if required else 1.0

    req_exp = ctx.get("required_experience_years", 0) or 1
    cand_exp = ctx.get("candidate_experience_years", 0)
    experience_ratio = min(cand_exp / req_exp, 1.0) if req_exp > 0 else 1.0

    jd_domain = (ctx.get("jd_domain") or "").lower()
    cand_domain = (ctx.get("candidate_domain") or "").lower()
    domain_match = 1.0 if (not jd_domain or jd_domain in cand_domain or cand_domain in jd_domain) else 0.0

    fit_score = (skills_ratio * 50) + (experience_ratio * 30) + (domain_match * 20)
    fit_score = round(fit_score, 1)

    threshold = ctx.get("threshold", 40)
    verdict = "qualified" if fit_score >= threshold else "unqualified"

    result = ScreeningResult(
        fit_score=fit_score,
        verdict=verdict,
        matched_skills=matched,
        missing_skills=missing,
        experience_match=cand_exp >= req_exp,
        breakdown={
            "skills_score": round(skills_ratio * 50, 1),
            "experience_score": round(experience_ratio * 30, 1),
            "domain_score": round(domain_match * 20, 1),
        },
    )
    return result.model_dump()


class ScreeningAgent(BaseAgent):
    name = "screening"

    def build_chain(self) -> Runnable:
        return RunnableLambda(_compute_fit_score)

    async def run(self, ctx: dict) -> dict:
        logger.debug("ScreeningAgent | required_skills={} candidate_skills={}",
                      len(ctx.get("required_skills", [])), len(ctx.get("candidate_skills", [])))
        result = _compute_fit_score(ctx)
        logger.info("ScreeningAgent complete | fit_score={} verdict={}",
                     result["fit_score"], result["verdict"])
        return result
