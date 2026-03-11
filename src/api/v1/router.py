from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.endpoints import health
from src.controllers.document_controller.document_controller import router as documents_router
from src.controllers.speech_controller.speech_controller import router as speech_router
from src.controllers.interview_controller.interview_controller import router as interview_router
from src.controllers.session_controller.session_controller import router as sessions_router
from src.controllers.candidate_controller.candidate_controller import router as candidates_router
from src.controllers.report_controller.report_controller import router as reports_router

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(candidates_router)
api_router.include_router(sessions_router)
api_router.include_router(documents_router)
api_router.include_router(speech_router)
api_router.include_router(interview_router)
api_router.include_router(reports_router)
