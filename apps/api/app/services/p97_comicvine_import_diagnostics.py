"""Structured stderr logging for P97 ComicVine queue/manual imports."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

LOGGER = logging.getLogger(__name__)


def log_import_event(message: str, *, enabled: bool = True) -> None:
    if not enabled:
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[p97-import {ts}] {message}"
    print(line, file=sys.stderr, flush=True)
    LOGGER.info("%s", line)
