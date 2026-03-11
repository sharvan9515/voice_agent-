from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.candidate import Candidate
from src.repositories.candidate import CandidateRepository
from src.schemas.candidate import CandidateCreate, CandidateUpdate
from src.utils.errors import ConflictError, NotFoundError
from src.utils.logger import logger


class CandidateService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = CandidateRepository(session)

    async def create_candidate(self, data: CandidateCreate) -> Candidate:
        logger.info("Creating candidate | email={email}", email=data.email)

        if await self.repo.exists_by_email(data.email):
            raise ConflictError(f"Candidate with email '{data.email}' already exists")

        candidate = Candidate(
            name=data.name,
            email=data.email,
            experience_level=data.experience_level,
            skill_scores=data.skill_scores,
        )
        return await self.repo.create(candidate)

    async def get_candidate(self, candidate_id: uuid.UUID) -> Candidate:
        candidate = await self.repo.get_by_id(candidate_id)
        if not candidate:
            raise NotFoundError(f"Candidate '{candidate_id}' not found")
        return candidate

    async def update_candidate(
        self, candidate_id: uuid.UUID, data: CandidateUpdate
    ) -> Candidate:
        candidate = await self.get_candidate(candidate_id)

        if data.email and data.email != candidate.email:
            if await self.repo.exists_by_email(data.email):
                raise ConflictError(f"Email '{data.email}' is already in use")
            candidate.email = data.email

        if data.name is not None:
            candidate.name = data.name
        if data.experience_level is not None:
            candidate.experience_level = data.experience_level
        if data.skill_scores is not None:
            candidate.skill_scores = data.skill_scores

        candidate.updated_at = datetime.now(timezone.utc)
        return await self.repo.update(candidate)

    async def upload_resume(
        self, candidate_id: uuid.UUID, file_bytes: bytes, content_type: str
    ) -> Candidate:
        from src.services.parsers.pdf_extractor import extract_text_from_pdf
        from src.services.parsers.resume_parser import parse_resume

        candidate = await self.repo.get_by_id(candidate_id)
        if not candidate:
            raise NotFoundError(f"Candidate '{candidate_id}' not found")

        if "pdf" in content_type.lower():
            raw_text = extract_text_from_pdf(file_bytes)
        else:
            raw_text = file_bytes.decode("utf-8", errors="ignore")

        parsed = await parse_resume(raw_text)
        candidate.resume_raw = raw_text
        candidate.resume_parsed = parsed.model_dump()
        return await self.repo.update(candidate)
