"""Structured logging for Collector Advisor proposal gather failures."""

from __future__ import annotations

import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


def log_advisor_gather_failure(*, subsystem: str, exc: BaseException) -> dict[str, Any]:
    """Log and return a structured record for ops diagnostics."""
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    last = tb[-1] if tb else None
    file_name = last.filename if last else ""
    line_no = last.lineno if last else 0
    record = {
        "subsystem": subsystem,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "file": file_name,
        "line": line_no,
    }
    logger.warning(
        "advisor_gather_subsystem_failed subsystem=%s exc_type=%s message=%s file=%s line=%s",
        subsystem,
        record["exception_type"],
        record["message"],
        record["file"],
        record["line"],
        exc_info=exc,
    )
    return record
