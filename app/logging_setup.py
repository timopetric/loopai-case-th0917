"""Logging — loguru, kept plain (architecture.md §4).

One stderr sink at a level taken from configuration. The standard library's
and uvicorn's own loggers are intercepted so every log line — ours and
uvicorn's — shares one format. No file sinks, no rotation, no request-id
middleware: the platform captures stderr and that is enough here.

Never log the shared API key, the OpenRouter key, or full prompts.
"""

import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route stdlib/uvicorn log records into loguru so formatting is unified."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(level: str = "INFO") -> None:
    """Install the single loguru stderr sink and intercept stdlib/uvicorn loggers."""
    logger.remove()
    logger.add(sys.stderr, level=level.upper(), backtrace=False, diagnose=False)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
    ):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False
