from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.api.v1.router import api_router
from src.config.database import connect_db, disconnect_db
from src.config.redis import connect_redis, disconnect_redis
from src.config.settings import settings
from src.middleware.error_handler import register_error_handlers
from src.utils.logger import logger, setup_logger

setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await connect_db()
    await connect_redis()
    logger.info("Ready | env={} port={}", settings.APP_ENV, settings.PORT)
    yield
    logger.info("Shutting down...")
    await disconnect_db()
    await disconnect_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice Interview Agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.API_PREFIX)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=settings.APP_ENV == "development")
