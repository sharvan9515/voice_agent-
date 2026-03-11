from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.deps import DbSession
from src.schemas.report import ReportExport, ReportResponse
from src.services.report import ReportService
from src.utils import response as resp

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{session_id}")
async def get_report(session_id: uuid.UUID, db: DbSession) -> JSONResponse:
    """Get the interview report for a session."""
    svc = ReportService(db)
    report = await svc.get_report(session_id)
    return resp.success(
        data=ReportResponse.model_validate(report).model_dump(mode="json"),
    )


@router.post("/{session_id}/generate")
async def generate_report(session_id: uuid.UUID, db: DbSession) -> JSONResponse:
    """Manually trigger report generation for a session."""
    svc = ReportService(db)
    report = await svc.generate_report(session_id)
    return resp.success(
        data=ReportResponse.model_validate(report).model_dump(mode="json"),
        message="Report generated successfully",
    )


@router.get("/{report_id}/export")
async def export_report(report_id: uuid.UUID, db: DbSession) -> JSONResponse:
    """Export a report as JSON by report ID."""
    svc = ReportService(db)
    export = await svc.export_report(report_id)
    return resp.success(
        data=export.model_dump(mode="json"),
        message="Report exported successfully",
    )
