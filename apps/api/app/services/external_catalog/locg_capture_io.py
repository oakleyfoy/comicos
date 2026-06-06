"""Windows-safe artifact writes for LoCG browser capture."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WINDOWS_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_path_segment(value: str) -> str:
    cleaned = _WINDOWS_INVALID_CHARS.sub("_", value.strip())
    return cleaned[:200] or "capture"


def capture_report_dir(base: Path, page_date_iso: str) -> Path:
    return base / sanitize_path_segment(page_date_iso)


def safe_write_text(path: Path, text: str, *, warnings: list[str], label: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        msg = f"{label}: {exc}"
        warnings.append(msg)
        logger.warning("locg artifact write failed: %s path=%s", msg, path)


def safe_write_json(path: Path, payload: Any, *, warnings: list[str], label: str) -> None:
    try:
        safe_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False), warnings=warnings, label=label)
    except Exception as exc:  # noqa: BLE001
        msg = f"{label}: {exc}"
        warnings.append(msg)
        logger.warning("locg artifact json failed: %s", msg)


def safe_browser_teardown(*, close_fn, warnings: list[str], label: str) -> None:
    try:
        close_fn()
    except OSError as exc:
        msg = f"{label}: {exc}"
        warnings.append(msg)
        logger.warning("locg browser teardown failed: %s", msg)
    except Exception as exc:  # noqa: BLE001
        msg = f"{label}: {exc}"
        warnings.append(msg)
        logger.warning("locg browser teardown failed: %s", msg)
