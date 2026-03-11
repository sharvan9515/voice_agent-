from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from src.api.deps import DbSession
from src.schemas.candidate import CandidateCreate, CandidateUpdate, CandidateResponse
from src.services.candidate import CandidateService
from src.utils import response as resp

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", status_code=201)
async def create_candidate(body: CandidateCreate, db: DbSession) -> JSONResponse:
    """Create a new candidate."""
    svc = CandidateService(db)
    candidate = await svc.create_candidate(body)
    return resp.created(
        data=CandidateResponse.model_validate(candidate).model_dump(mode="json"),
        message="Candidate created successfully",
    )


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: uuid.UUID, db: DbSession) -> JSONResponse:
    """Retrieve a candidate by ID."""
    svc = CandidateService(db)
    candidate = await svc.get_candidate(candidate_id)
    return resp.success(
        data=CandidateResponse.model_validate(candidate).model_dump(mode="json"),
    )


@router.put("/{candidate_id}")
async def update_candidate(
    candidate_id: uuid.UUID,
    body: CandidateUpdate,
    db: DbSession,
) -> JSONResponse:
    """Update a candidate's information."""
    svc = CandidateService(db)
    candidate = await svc.update_candidate(candidate_id, body)
    return resp.success(
        data=CandidateResponse.model_validate(candidate).model_dump(mode="json"),
        message="Candidate updated successfully",
    )


@router.post("/{candidate_id}/resume", response_model=None)
async def upload_resume(
    candidate_id: uuid.UUID,
    db: DbSession,
    file: UploadFile = File(...),
) -> JSONResponse:
    """Upload a candidate's resume (PDF or plain text). Text is extracted and parsed via Claude."""
    svc = CandidateService(db)
    candidate = await svc.upload_resume(
        candidate_id,
        await file.read(),
        file.content_type or "application/pdf",
    )
    return resp.success(
        data={"id": str(candidate.id), "resume_parsed": candidate.resume_parsed},
        message="Resume uploaded and parsed",
    )
