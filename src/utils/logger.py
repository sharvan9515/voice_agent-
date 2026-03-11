from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from src.config.settings import settings


def setup_logger() -> None:
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
        enqueue=True,
    )

    # File handler — rotated daily, retained 30 days
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        rotation="00:00",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # Error-only file
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}\n{exception}"
        ),
        rotation="00:00",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )


__all__ = ["logger", "setup_logger"]
