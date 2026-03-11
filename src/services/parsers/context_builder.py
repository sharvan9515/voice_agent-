from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.schemas.job import ParsedJD
from src.services.parsers.resume_parser import ParsedResume


class InterviewContext(BaseModel):
    job_title: str
    company: Optional[str] = None
    domain: str
    seniority_level: str
    required_skills: list[str]
    candidate_skills: list[str]
    matched_skills: list[str]
    skill_gaps: list[str]
    bonus_skills: list[str]
    required_experience_years: int
    candidate_experience_years: float
    experience_gap: bool
    jd_summary: str
    resume_summary: str


def build_context(jd: ParsedJD, resume: ParsedResume) -> InterviewContext:
    req = {s.lower() for s in jd.required_skills}
    cand = {s.lower() for s in resume.skills}

    matched = sorted(req & cand)
    gaps = sorted(req - cand)
    bonus = sorted(cand - req)

    jd_summary = (
        f"Role: {jd.title}" + (f" at {jd.company}" if jd.company else "") + "\n"
        f"Domain: {jd.domain} | Seniority: {jd.seniority_level}\n"
        f"Required skills: {', '.join(jd.required_skills)}\n"
        f"Nice to have: {', '.join(jd.nice_to_have)}\n"
        f"Min experience: {jd.min_experience_years} years\n"
        f"Key responsibilities: {'; '.join(jd.responsibilities[:4])}"
    )

    resume_summary = (
        f"Candidate skills: {', '.join(resume.skills)}\n"
        f"Total experience: {resume.total_experience_years} years\n"
        f"Matched skills: {', '.join(matched) or 'none'}\n"
        f"Skill gaps: {', '.join(gaps) or 'none'}\n"
        f"Recent role: {resume.experience[0]['title'] if resume.experience else 'N/A'}"
    )

    return InterviewContext(
        job_title=jd.title,
        company=jd.company,
        domain=jd.domain,
        seniority_level=jd.seniority_level,
        required_skills=jd.required_skills,
        candidate_skills=resume.skills,
        matched_skills=matched,
        skill_gaps=gaps,
        bonus_skills=bonus,
        required_experience_years=jd.min_experience_years,
        candidate_experience_years=resume.total_experience_years,
        experience_gap=resume.total_experience_years < jd.min_experience_years,
        jd_summary=jd_summary,
        resume_summary=resume_summary,
    )
