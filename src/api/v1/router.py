from __future__ import annotations

from fastapi import APIRouter

from src.api.v1.endpoints import (
    candidates,
    health,
    interviews,
    jobs,
    reports,
    sessions,
    speech,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(candidates.router)
api_router.include_router(sessions.router)
api_router.include_router(interviews.router)
api_router.include_router(speech.router)
api_router.include_router(reports.router)
api_router.include_router(jobs.router)
