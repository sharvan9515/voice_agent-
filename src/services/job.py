from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job import Job
from src.repositories.job import JobRepository
from src.schemas.job import JobCreate, ParsedJD
from src.services.parsers.jd_parser import parse_jd
from src.services.parsers.pdf_extractor import extract_text_from_pdf
from src.utils.errors import NotFoundError
from src.utils.logger import logger


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = JobRepository(db)

    async def create_job(self, data: JobCreate) -> Job:
        logger.info("Parsing JD for: {}", data.title)
        parsed = await parse_jd(data.description_raw)
        job = Job(
            title=data.title,
            company=data.company,
            description_raw=data.description_raw,
            description_parsed=parsed.model_dump(),
        )
        return await self.repo.create(job)

    async def get_job(self, job_id: uuid.UUID) -> Job:
        job = await self.repo.get_by_id(job_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found")
        return job

    async def create_job_from_pdf(
        self, file_bytes: bytes, title: str, company: Optional[str] = None
    ) -> Job:
        raw_text = extract_text_from_pdf(file_bytes)
        return await self.create_job(
            JobCreate(title=title, company=company, description_raw=raw_text)
        )
