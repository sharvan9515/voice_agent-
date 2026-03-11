from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.openai_client import chat_json
from src.models.interview_report import InterviewReport
from src.repositories.record import RecordRepository
from src.repositories.report import ReportRepository
from src.repositories.session import SessionRepository
from src.schemas.report import ReportExport, ReportResponse
from src.utils.errors import ExternalServiceError, NotFoundError
from src.utils.logger import logger

REPORT_SYSTEM_PROMPT = """You are an expert technical interview assessor writing a comprehensive candidate evaluation report.
Based on the interview data provided, generate a professional narrative summary.

You MUST respond with ONLY valid JSON in the following format:
{
  "summary": "<detailed narrative summary paragraph>",
  "overall_strengths": ["<strength 1>", "<strength 2>", ...],
  "overall_weaknesses": ["<weakness 1>", "<weakness 2>", ...]
}

Do not include any text outside the JSON object."""


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.report_repo = ReportRepository(db)
        self.record_repo = RecordRepository(db)
        self.session_repo = SessionRepository(db)

    async def generate_report(self, session_id: uuid.UUID) -> InterviewReport:
        logger.info("Generating report | session_id={sid}", sid=session_id)

        # Check if report already exists
        existing = await self.report_repo.get_by_session_id(session_id)
        if existing:
            logger.info("Report already exists | report_id={rid}", rid=existing.id)
            return existing

        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session '{session_id}' not found")

        records = await self.record_repo.get_by_session_with_evaluations(session_id)

        if not records:
            raise NotFoundError("No interview records found for this session")

        scores = [r.evaluation.score for r in records if r.evaluation]
        total_score = sum(scores) / len(scores) if scores else 0.0

        all_strengths: List[str] = []
        all_weaknesses: List[str] = []
        for record in records:
            if record.evaluation:
                all_strengths.extend(record.evaluation.strengths or [])
                all_weaknesses.extend(record.evaluation.weaknesses or [])

        # Deduplicate
        unique_strengths = list(dict.fromkeys(all_strengths))[:10]
        unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:10]

        # Build interview summary for Claude
        interview_summary = []
        for i, record in enumerate(records, 1):
            eval_info = ""
            if record.evaluation:
                eval_info = f"Score: {record.evaluation.score}/10. Feedback: {record.evaluation.feedback}"
            interview_summary.append(
                f"Q{i} ({record.question_skill} - {record.question_difficulty}): {record.question_text}\n"
                f"Answer: {record.candidate_answer}\n"
                f"Evaluation: {eval_info}"
            )

        narrative = await self._generate_narrative(
            interview_summary="\n\n".join(interview_summary),
            total_score=total_score,
            strengths=unique_strengths,
            weaknesses=unique_weaknesses,
        )

        report = InterviewReport(
            session_id=session_id,
            candidate_id=session.candidate_id,
            total_score=total_score,
            strengths=narrative["overall_strengths"],
            weaknesses=narrative["overall_weaknesses"],
            summary=narrative["summary"],
        )
        report = await self.report_repo.create(report)
        logger.info("Report generated | report_id={rid} | score={score}", rid=report.id, score=total_score)
        return report

    async def _generate_narrative(
        self,
        interview_summary: str,
        total_score: float,
        strengths: List[str],
        weaknesses: List[str],
    ) -> dict:
        user_prompt = f"""Generate a comprehensive evaluation report for a candidate interview.

OVERALL SCORE: {total_score:.1f}/10

INTERVIEW TRANSCRIPT SUMMARY:
{interview_summary}

OBSERVED STRENGTHS: {json.dumps(strengths)}
OBSERVED WEAKNESSES: {json.dumps(weaknesses)}

Write a professional narrative summary and refine the strengths/weaknesses lists.
Return ONLY the JSON object."""

        try:
            return await chat_json(REPORT_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            logger.error("Report narrative generation error: {}", str(exc))
            # Return fallback narrative
            return {
                "summary": (
                    f"The candidate completed the interview with an overall score of "
                    f"{total_score:.1f}/10. "
                    f"They demonstrated competency in several areas while having room for improvement in others."
                ),
                "overall_strengths": strengths,
                "overall_weaknesses": weaknesses,
            }

    async def get_report(self, session_id: uuid.UUID) -> InterviewReport:
        report = await self.report_repo.get_by_session_id(session_id)
        if not report:
            raise NotFoundError(f"No report found for session '{session_id}'")
        return report

    async def export_report(self, report_id: uuid.UUID) -> ReportExport:
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError(f"Report '{report_id}' not found")

        records = await self.record_repo.get_by_session_with_evaluations(report.session_id)
        records_data = []
        for r in records:
            record_dict = {
                "id": str(r.id),
                "question_id": r.question_id,
                "question_text": r.question_text,
                "question_skill": r.question_skill,
                "question_difficulty": r.question_difficulty,
                "candidate_answer": r.candidate_answer,
                "timestamp": r.timestamp.isoformat(),
                "evaluation": None,
            }
            if r.evaluation:
                record_dict["evaluation"] = {
                    "score": r.evaluation.score,
                    "feedback": r.evaluation.feedback,
                    "strengths": r.evaluation.strengths,
                    "weaknesses": r.evaluation.weaknesses,
                }
            records_data.append(record_dict)

        return ReportExport(
            report_id=report.id,
            session_id=report.session_id,
            candidate_id=report.candidate_id,
            total_score=report.total_score,
            strengths=report.strengths,
            weaknesses=report.weaknesses,
            summary=report.summary,
            records=records_data,
            created_at=report.created_at.isoformat(),
            exported_at=datetime.now(timezone.utc).isoformat(),
        )
