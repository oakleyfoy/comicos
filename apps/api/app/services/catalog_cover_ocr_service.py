from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session

from app.core.config import get_settings
from app.models.catalog_master import CatalogOcrMetadata, utc_now
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name

LOGGER = logging.getLogger(__name__)

_OCR_ISSUE = re.compile(r"(?<!\d)(\d{1,4}(?:\.\d+)?|\d+\s*/\s*\d+)(?!\d)")

MISSING_PYTESSERACT = "MISSING_PYTESSERACT"
MISSING_PILLOW = "MISSING_PILLOW"
MISSING_TESSERACT_BINARY = "MISSING_TESSERACT_BINARY"
OCR_DISABLED = "OCR_DISABLED"
MISSING_LOCAL_IMAGE = "MISSING_LOCAL_IMAGE"
OCR_EMPTY_RESULT = "OCR_EMPTY_RESULT"
OCR_EXCEPTION = "OCR_EXCEPTION"


@dataclass(frozen=True)
class OcrExtractResult:
    text: str | None
    skip_reason: str | None = None
    detail: str | None = None


def parse_ocr_metadata(text: str) -> dict[str, str | None]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    if lines:
        series = lines[0].title()
    for line in lines[1:]:
        upper = line.upper()
        if "COMICS" in upper or upper in {"MARVEL", "DC", "IMAGE", "DARK HORSE"}:
            publisher = line.title()
            continue
        match = _OCR_ISSUE.search(line)
        if match and issue_number is None:
            issue_number = normalize_issue_number(match.group(1))
    return {
        "extracted_series": series,
        "extracted_issue_number": issue_number,
        "extracted_publisher": publisher,
        "confidence": "0.75" if series and issue_number else "0.55",
    }


def pillow_installed() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def pytesseract_installed() -> bool:
    try:
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_tesseract_binary() -> str | None:
    settings = get_settings()
    configured = (settings.tesseract_cmd or "").strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path.resolve())
        found = shutil.which(configured)
        if found:
            return found
        return configured
    return shutil.which("tesseract")


def tesseract_version(binary: str | None = None) -> str | None:
    cmd = binary or resolve_tesseract_binary()
    if not cmd:
        return None
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = (result.stdout or "").splitlines()
    if not lines:
        return None
    return lines[0].strip() or None


def _configure_pytesseract_cmd() -> str | None:
    import pytesseract  # type: ignore

    binary = resolve_tesseract_binary()
    if binary:
        pytesseract.pytesseract.tesseract_cmd = binary
    return binary


def extract_ocr_from_image_path(path: str) -> str | None:
    """Legacy helper; prefer ``extract_ocr_from_image_path_result`` for skip reasons."""
    return extract_ocr_from_image_path_result(path).text


def extract_ocr_from_image_path_result(path: str) -> OcrExtractResult:
    settings = get_settings()
    if not settings.ocr_enabled:
        return OcrExtractResult(None, skip_reason=OCR_DISABLED, detail="OCR_ENABLED is false")

    if not pillow_installed():
        return OcrExtractResult(None, skip_reason=MISSING_PILLOW)

    if not pytesseract_installed():
        return OcrExtractResult(None, skip_reason=MISSING_PYTESSERACT)

    image_path = Path(path)
    if not path or not image_path.is_file():
        return OcrExtractResult(None, skip_reason=MISSING_LOCAL_IMAGE, detail=path or "(empty path)")

    binary = resolve_tesseract_binary()
    if not binary or not Path(binary).is_file() and shutil.which(binary) is None:
        if not shutil.which("tesseract") and not (Path(binary).is_file() if binary else False):
            return OcrExtractResult(
                None,
                skip_reason=MISSING_TESSERACT_BINARY,
                detail=binary or "tesseract not on PATH",
            )

    try:
        import pytesseract  # type: ignore
        from PIL import Image

        _configure_pytesseract_cmd()
        with Image.open(image_path) as img:
            raw = pytesseract.image_to_string(img)
    except Exception as exc:
        return OcrExtractResult(None, skip_reason=OCR_EXCEPTION, detail=str(exc)[:500])

    normalized = (raw or "").strip()
    if not normalized:
        return OcrExtractResult(None, skip_reason=OCR_EMPTY_RESULT)

    return OcrExtractResult(normalized)


def log_ocr_skip(*, image_id: int | None, reason: str, detail: str | None = None) -> None:
    if detail:
        LOGGER.info("ocr skip image_id=%s reason=%s detail=%s", image_id, reason, detail)
    else:
        LOGGER.info("ocr skip image_id=%s reason=%s", image_id, reason)


def store_ocr_for_image(
    session: Session,
    *,
    image_id: int,
    issue_id: int | None,
    variant_id: int | None,
    ocr_text: str,
) -> CatalogOcrMetadata:
    parsed = parse_ocr_metadata(ocr_text)
    row = CatalogOcrMetadata(
        image_id=image_id,
        issue_id=issue_id,
        variant_id=variant_id,
        ocr_text=ocr_text,
        extracted_series=parsed.get("extracted_series"),
        extracted_issue_number=parsed.get("extracted_issue_number"),
        extracted_publisher=parsed.get("extracted_publisher"),
        confidence=Decimal(str(parsed.get("confidence") or "0.5")),
    )
    session.add(row)
    session.flush()
    return row


def search_issues_by_ocr_fields(session: Session, *, series: str | None, issue_number: str | None, publisher: str | None):
    from sqlmodel import select

    from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries

    statement = select(CatalogIssue).join(CatalogSeries, CatalogSeries.id == CatalogIssue.series_id)
    rows = session.exec(statement).all()
    norm_series = normalize_series_name(series or "")
    norm_issue = normalize_issue_number(issue_number or "")
    norm_pub = normalize_series_name(publisher or "")
    hits = []
    for issue in rows:
        series_row = session.get(CatalogSeries, issue.series_id)
        if series_row is None:
            continue
        pub = session.get(CatalogPublisher, issue.publisher_id or series_row.publisher_id or 0)
        if norm_series and normalize_series_name(series_row.name) != norm_series:
            continue
        if norm_issue and issue.normalized_issue_number != norm_issue:
            continue
        if norm_pub and pub and normalize_series_name(pub.name) != norm_pub:
            continue
        hits.append(issue)
    return hits
