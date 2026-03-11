from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.deps import DbSession, RedisClient
from src.utils.logger import logger

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: DbSession, redis: RedisClient) -> JSONResponse:
    db_ok, redis_ok = True, True
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("DB health check failed: {}", e)
        db_ok = False
    try:
        await redis.ping()
    except Exception as e:
        logger.error("Redis health check failed: {}", e)
        redis_ok = False

    ok = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "success": ok,
            "status": "ok" if ok else "degraded",
            "services": {"database": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "error"},
        },
    )
