"""InterviewOrchestrator — wires all agents together using LangChain RunnableParallel."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from langchain_core.runnables import RunnableParallel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.director_agent import DirectorAgent
from src.agents.evaluator_agent import EvaluatorAgent
from src.agents.jd_parser_agent import JDParserAgent
from src.agents.report_agent import ReportAgent
from src.agents.resume_parser_agent import ResumeParserAgent
from src.agents.screening_agent import ScreeningAgent
from sqlalchemy import select

from src.models.candidate import Candidate
from src.models.conversation_log import ConversationLog
from src.models.evaluation_result import EvaluationResult
from src.models.interview_record import InterviewRecord
from src.models.interview_session import InterviewSession, SessionStatus
from src.models.job import Job
from src.repositories.candidate import CandidateRepository
from src.repositories.job import JobRepository
from src.repositories.record import RecordRepository
from src.repositories.report import ReportRepository
from src.repositories.session import SessionRepository
from src.schemas.interview_config import InterviewConfig
from src.schemas.session import SessionState
from src.services.parsers.context_builder import build_context
from src.services.parsers.pdf_extractor import extract_text_from_pdf
from src.services.parsers.resume_parser import ParsedResume
from src.schemas.job import ParsedJD
from src.services.session import SessionService
from src.utils.logger import logger


class InterviewOrchestrator:
    """Central orchestrator: setup_interview, process_answer, evaluate_and_report."""

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.session_svc = SessionService(db, redis)
        self.candidate_repo = CandidateRepository(db)
        self.job_repo = JobRepository(db)
        self.session_repo = SessionRepository(db)
        self.record_repo = RecordRepository(db)
        self.report_repo = ReportRepository(db)

        # Agents
        self.resume_parser = ResumeParserAgent()
        self.jd_parser = JDParserAgent()
        self.screening = ScreeningAgent()
        self.director = DirectorAgent()
        self.evaluator = EvaluatorAgent()
        self.report_agent = ReportAgent()

    async def setup_interview(
        self,
        file_bytes: bytes,
        content_type: str,
        jd_text: str,
        config_dict: Optional[dict] = None,
    ) -> dict:
        """
        One-shot interview setup:
        1. Parse resume + JD concurrently (LangChain agents)
        2. Build context via context_builder
        3. Run screening (pure math)
        4. If fit_score < threshold → return screening result, no session
        5. Create candidate + job + session in DB
        6. Director agent → first question
        7. Return full setup response
        """
        config = InterviewConfig(**(config_dict or {}))

        # 1. Extract raw text from resume
        if "pdf" in content_type.lower():
            raw_resume_text = extract_text_from_pdf(file_bytes)
            if not raw_resume_text.strip():
                raise ValueError(
                    "Could not extract text from PDF. "
                    "The file may be scanned/image-only."
                )
        else:
            raw_resume_text = file_bytes.decode("utf-8", errors="ignore")

        # 2. Parse resume + JD concurrently via LangChain agents
        resume_task = self.resume_parser.run({"raw_text": raw_resume_text})
        jd_task = self.jd_parser.run({"raw_text": jd_text})
        parsed_resume_dict, parsed_jd_dict = await asyncio.gather(resume_task, jd_task)

        parsed_resume = ParsedResume(**parsed_resume_dict)
        parsed_jd = ParsedJD(**parsed_jd_dict)

        # 3. Build context
        interview_context = build_context(parsed_jd, parsed_resume)
        ctx_dict = interview_context.model_dump()

        # 4. Screening (instant, pure math)
        screening_result = await self.screening.run({
            "required_skills": parsed_jd.required_skills,
            "candidate_skills": parsed_resume.skills,
            "required_experience_years": parsed_jd.min_experience_years,
            "candidate_experience_years": parsed_resume.total_experience_years,
            "jd_domain": parsed_jd.domain,
            "candidate_domain": "",
            "threshold": config.screen_threshold,
        })

        if screening_result["verdict"] == "unqualified":
            logger.info("Screening rejected candidate | fit_score={}",
                        screening_result["fit_score"])
            return {
                "status": "screened_out",
                "screening": screening_result,
                "candidate": {
                    "name": parsed_resume.name,
                    "email": parsed_resume.email,
                    "skills": parsed_resume.skills,
                    "experience_years": parsed_resume.total_experience_years,
                },
                "config": config.model_dump(),
            }

        # 5. Create candidate + job + session in DB
        # Candidate
        name = parsed_resume.name or "Unknown Candidate"
        email = parsed_resume.email or f"candidate_{uuid.uuid4().hex[:8]}@interview.local"
        years = parsed_resume.total_experience_years or 0.0
        if years < 2:
            exp_level = "junior"
        elif years < 5:
            exp_level = "mid"
        elif years < 8:
            exp_level = "senior"
        elif years < 12:
            exp_level = "lead"
        else:
            exp_level = "principal"

        if await self.candidate_repo.exists_by_email(email):
            email = f"{uuid.uuid4().hex[:6]}_{email}"

        candidate = Candidate(
            name=name,
            email=email,
            experience_level=exp_level,
            skill_scores={},
            resume_raw=raw_resume_text,
            resume_parsed=parsed_resume_dict,
        )
        candidate = await self.candidate_repo.create(candidate)

        # Job
        job = Job(
            title=parsed_jd.title or "General Interview",
            company=parsed_jd.company,
            description_raw=jd_text,
            description_parsed=parsed_jd_dict,
        )
        job = await self.job_repo.create(job)

        # Session
        from src.schemas.session import SessionCreate
        session = await self.session_svc.create_session(
            SessionCreate(candidate_id=candidate.id, job_id=job.id)
        )

        # Update state with config + interview_config
        state = await self.session_svc.get_session_state(session.id)
        state.interview_config = config.model_dump()
        state.status = SessionStatus.IN_PROGRESS.value

        # Mark session in-progress
        session.status = SessionStatus.IN_PROGRESS
        await self.session_repo.update(session)

        # 6. Director agent → first question
        opening = await self.director.generate_opening({
            "state": state,
            "config": config.model_dump(),
        })

        question_id = str(uuid.uuid4())
        question_text = opening["question_text"]
        topic = opening["topic"]

        state.current_question = {
            "question_id": question_id,
            "text": question_text,
            "topic": topic,
            "skill": topic,
            "difficulty": ctx_dict.get("seniority_level", "intermediate"),
        }
        state.conversation_history.append({
            "role": "agent",
            "content": question_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        state.current_topic = topic
        await self.session_svc.update_session_state(state)

        await self.db.commit()

        return {
            "status": "ready",
            "session_id": str(session.id),
            "realtime_ws_url": f"/api/v1/interview/{session.id}/realtime",
            "candidate": {
                "id": str(candidate.id),
                "name": candidate.name,
                "email": candidate.email,
                "experience_level": candidate.experience_level,
            },
            "screening": screening_result,
            "first_question": {
                "question_id": question_id,
                "text": question_text,
                "topic": topic,
            },
            "config": config.model_dump(),
        }

    async def process_answer(self, state: SessionState, transcript: str) -> dict:
        """
        Process a candidate answer:
        1. Run evaluator + director concurrently (LangChain agents)
        2. Update topic tracking in state
        3. Return evaluation + decision + updated_state
        """
        current_q = state.current_question or {}
        config_dict = state.interview_config or {}
        config = InterviewConfig(**config_dict) if config_dict else InterviewConfig()

        # Run evaluator + director concurrently
        eval_task = self.evaluator.run({
            "question_text": current_q.get("text", ""),
            "candidate_answer": transcript,
            "question_skill": current_q.get("skill", "general"),
            "question_difficulty": current_q.get("difficulty", "intermediate"),
            "jd_context": state.jd_context,
        })
        director_task = self.director.run({
            "state": state,
            "latest_transcript": transcript,
            "max_questions": config.max_questions,
            "config": config_dict,
        })

        eval_result, decision = await asyncio.gather(
            eval_task, director_task, return_exceptions=True
        )

        # Handle evaluation failure gracefully
        if isinstance(eval_result, Exception):
            logger.warning("Evaluation failed (non-fatal): {}", eval_result)
            eval_result = {
                "score": 5.0,
                "feedback": "Evaluation unavailable",
                "strengths": [],
                "weaknesses": [],
            }

        if isinstance(decision, Exception):
            raise decision

        # Update topic tracking
        action = decision["action"]
        new_topic = decision.get("topic", "general")

        if action == "follow_up":
            state.follow_ups_this_topic += 1
        elif action == "next_question":
            if state.current_topic and state.current_topic not in state.topics_covered:
                state.topics_covered.append(state.current_topic)
            state.current_topic = new_topic
            state.follow_ups_this_topic = 0

        return {
            "evaluation": eval_result,
            "decision": decision,
            "state": state,
        }

    async def evaluate_and_report(self, session_id: uuid.UUID) -> dict:
        """
        Post-interview pipeline:
        1. Extract Q&A pairs from ConversationLog
        2. Run EvaluatorAgent on each pair (concurrently)
        3. Persist InterviewRecord + EvaluationResult for each
        4. Compute avg score, end session
        5. Run ReportAgent → narrative
        6. Persist report
        """
        from src.models.interview_report import InterviewReport

        # 1. Extract Q&A pairs from conversation logs
        state = await self.session_svc.get_session_state(session_id)
        qa_pairs = self._extract_qa_pairs(state)

        if not qa_pairs:
            logger.warning("No Q&A pairs found | session={}", session_id)
            await self.session_svc.end_session(session_id, total_score=0.0)
            await self.db.commit()
            return {"total_score": 0.0, "summary": "No questions were answered."}

        jd_context = state.jd_context or {}

        # 2. Run EvaluatorAgent on each Q&A pair concurrently
        eval_tasks = []
        for qa in qa_pairs:
            eval_tasks.append(self.evaluator.run({
                "question_text": qa["question"],
                "candidate_answer": qa["answer"],
                "question_skill": qa.get("topic", "general"),
                "question_difficulty": "intermediate",
                "jd_context": jd_context,
            }))

        eval_results = await asyncio.gather(*eval_tasks, return_exceptions=True)

        # 3. Persist InterviewRecord + EvaluationResult for each pair
        all_strengths = []
        all_weaknesses = []
        interview_summary_parts = []
        scores = []

        for i, (qa, eval_result) in enumerate(zip(qa_pairs, eval_results), 1):
            # Handle evaluation failure gracefully
            if isinstance(eval_result, Exception):
                logger.warning("Evaluation failed for Q{}: {}", i, eval_result)
                eval_result = {
                    "score": 5.0,
                    "feedback": "Evaluation unavailable",
                    "strengths": [],
                    "weaknesses": [],
                }

            score = max(0.0, min(10.0, float(eval_result.get("score", 5.0))))
            scores.append(score)

            # Persist InterviewRecord
            record = InterviewRecord(
                session_id=session_id,
                question_id=str(uuid.uuid4()),
                question_text=qa["question"],
                question_skill=qa.get("topic", "general"),
                question_difficulty="intermediate",
                candidate_answer=qa["answer"],
            )
            record = await self.record_repo.create(record)

            # Persist EvaluationResult
            strengths = eval_result.get("strengths", [])
            weaknesses = eval_result.get("weaknesses", [])
            self.db.add(EvaluationResult(
                record_id=record.id,
                score=score,
                feedback=eval_result.get("feedback", ""),
                strengths=strengths,
                weaknesses=weaknesses,
            ))

            all_strengths.extend(strengths)
            all_weaknesses.extend(weaknesses)
            interview_summary_parts.append(
                f"Q{i} ({qa.get('topic', 'general')}): {qa['question']}\n"
                f"Answer: {qa['answer']}\n"
                f"Evaluation: Score: {score}/10. Feedback: {eval_result.get('feedback', '')}"
            )

        await self.db.flush()

        # 4. Compute avg score, end session
        avg_score = sum(scores) / len(scores) if scores else 0.0
        await self.session_svc.end_session(session_id, total_score=avg_score)
        await self.db.commit()

        logger.info("Post-interview evaluation complete | session={} | pairs={} | avg_score={}",
                     session_id, len(qa_pairs), avg_score)

        # 5. Run report agent
        unique_strengths = list(dict.fromkeys(all_strengths))[:10]
        unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:10]

        narrative = await self.report_agent.run({
            "total_score": avg_score,
            "interview_summary": "\n\n".join(interview_summary_parts),
            "strengths": unique_strengths,
            "weaknesses": unique_weaknesses,
        })

        # 6. Persist report
        session = await self.session_repo.get_by_id(session_id)
        report = InterviewReport(
            session_id=session_id,
            candidate_id=session.candidate_id,
            total_score=avg_score,
            strengths=narrative.get("overall_strengths", unique_strengths),
            weaknesses=narrative.get("overall_weaknesses", unique_weaknesses),
            summary=narrative.get("summary", ""),
        )
        report = await self.report_repo.create(report)
        await self.db.commit()

        logger.info("Report generated | report_id={} | score={}", report.id, avg_score)
        return {
            "report_id": str(report.id),
            "total_score": avg_score,
            "summary": report.summary,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
        }

    @staticmethod
    def _extract_qa_pairs(state: SessionState) -> list[dict]:
        """
        Extract Q&A pairs from conversation history.

        Pairs an agent message (question) with the following candidate message (answer).
        Skips the opening greeting and any unpaired messages.
        """
        history = state.conversation_history or []
        pairs = []
        pending_question = None

        for entry in history:
            role = entry.get("role", "")
            content = entry.get("content", "").strip()
            if not content:
                continue

            if role == "agent":
                # If there's a pending question without an answer, discard it
                # (e.g., a greeting or transition statement)
                pending_question = content
            elif role == "candidate" and pending_question:
                # Check if the agent message looks like a question (contains ?)
                # or is substantive enough to be one
                if "?" in pending_question or len(pending_question) > 40:
                    pairs.append({
                        "question": pending_question,
                        "answer": content,
                        "topic": "general",
                    })
                pending_question = None

        return pairs
