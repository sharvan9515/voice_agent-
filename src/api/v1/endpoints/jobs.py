from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from src.api.deps import DbSession
from src.schemas.job import JobCreate, JobResponse
from src.services.job import JobService
from src.utils.response import success

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=None)
async def create_job(data: JobCreate, db: DbSession):
    """Create a job by submitting raw JD text. Automatically parses the JD via Claude."""
    svc = JobService(db)
    job = await svc.create_job(data)
    return success(JobResponse.model_validate(job).model_dump(mode="json"), "Job created and JD parsed")


@router.get("/{job_id}", response_model=None)
async def get_job(job_id: UUID, db: DbSession):
    """Retrieve a job by ID."""
    svc = JobService(db)
    job = await svc.get_job(job_id)
    return success(JobResponse.model_validate(job).model_dump(mode="json"))


@router.post("/upload", response_model=None)
async def upload_jd_pdf(
    db: DbSession,
    file: UploadFile = File(...),
    title: str = Form(...),
    company: Optional[str] = Form(None),
):
    """Upload a JD as a PDF file. Text is extracted and parsed via Claude."""
    svc = JobService(db)
    file_bytes = await file.read()
    job = await svc.create_job_from_pdf(file_bytes, title=title, company=company)
    return success(
        JobResponse.model_validate(job).model_dump(mode="json"),
        "JD PDF parsed and job created",
    )
