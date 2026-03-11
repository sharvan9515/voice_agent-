"""
Document Controller
-------------------
Handles document ingestion for the interview pipeline.

Routes:
  POST /api/v1/documents/job-description   — Upload JD as PDF or paste raw text
  POST /api/v1/documents/job-description/upload — Upload JD as PDF file
  GET  /api/v1/documents/job-description/{job_id} — Retrieve parsed JD
  POST /api/v1/documents/resume/{candidate_id}    — Upload candidate resume (PDF / text)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from typing import Optional

from src.api.deps import DbSession
from src.schemas.job import JobCreate, JobResponse
from src.services.job import JobService
from src.services.candidate import CandidateService
from src.utils import response as resp
from src.utils.errors import ValidationError

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_DOC_TYPES = {"application/pdf", "text/plain"}


# ── Job Description ────────────────────────────────────────────────────────────

@router.post(
    "/job-description",
    status_code=201,
    summary="Create job description from text",
    description="Submit a job description as plain text. The system parses it into structured data "
                "(required skills, responsibilities, seniority level, domain) and stores it.",
)
async def create_job_description(body: JobCreate, db: DbSession) -> JSONResponse:
    svc = JobService(db)
    job = await svc.create_job(body)
    return resp.created(
        data=JobResponse.model_validate(job).model_dump(mode="json"),
        message="Job description parsed and stored successfully",
    )


@router.post(
    "/job-description/upload",
    status_code=201,
    summary="Upload job description as PDF",
    description="Upload a PDF file containing the job description. Text is extracted automatically "
                "and parsed into structured data by the AI pipeline.",
)
async def upload_job_description_pdf(
    db: DbSession,
    file: UploadFile = File(..., description="Job description PDF file"),
    title: str = Form(..., description="Job title"),
    company: Optional[str] = Form(None, description="Company name (optional)"),
) -> JSONResponse:
    content_type = file.content_type or "application/pdf"
    if content_type not in ALLOWED_DOC_TYPES:
        raise ValidationError("Only PDF and plain text files are supported for job descriptions")

    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationError("Uploaded file is empty")

    svc = JobService(db)
    job = await svc.create_job_from_pdf(file_bytes, title=title, company=company)
    return resp.created(
        data=JobResponse.model_validate(job).model_dump(mode="json"),
        message="Job description PDF processed and parsed successfully",
    )


@router.get(
    "/job-description/{job_id}",
    summary="Retrieve a parsed job description",
    description="Fetch a previously uploaded and parsed job description by its ID.",
)
async def get_job_description(job_id: uuid.UUID, db: DbSession) -> JSONResponse:
    svc = JobService(db)
    job = await svc.get_job(job_id)
    return resp.success(data=JobResponse.model_validate(job).model_dump(mode="json"))


# ── Resume ─────────────────────────────────────────────────────────────────────

@router.post(
    "/resume/{candidate_id}",
    summary="Upload and parse candidate resume",
    description="Upload a candidate's resume as a PDF or plain text file. "
                "The AI pipeline extracts skills, experience, education, and projects "
                "into a structured format used to personalise the interview questions.",
)
async def upload_resume(
    candidate_id: uuid.UUID,
    db: DbSession,
    file: UploadFile = File(..., description="Resume file (PDF or .txt)"),
) -> JSONResponse:
    content_type = file.content_type or "application/pdf"
    if content_type not in ALLOWED_DOC_TYPES:
        raise ValidationError("Only PDF and plain text files are supported for resumes")

    file_bytes = await file.read()
    if not file_bytes:
        raise ValidationError("Uploaded file is empty")

    svc = CandidateService(db)
    candidate = await svc.upload_resume(candidate_id, file_bytes, content_type)
    return resp.success(
        data={
            "candidate_id": str(candidate.id),
            "resume_parsed": candidate.resume_parsed,
        },
        message="Resume uploaded and parsed successfully",
    )
