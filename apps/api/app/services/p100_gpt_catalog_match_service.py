"""Local catalog match for standalone GPT Comic Read (text + optional UPC)."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.services.catalog_ingestion_service import normalize_upc, upc_check_digit_valid
from app.services.gpt_comic_read_service import GptComicReadResult
from app.services.recognition.catalog_matcher import load_catalog_issue_identity
from app.services.recognition.recognition_catalog_candidate_service import search_catalog_candidates

logger = logging.getLogger(__name__)


@dataclass
class P100CatalogMatch:
    matched: bool = False
    catalog_issue_id: int | None = None
    method: str = "none"
    confidence: float | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    cover_image_url: str | None = None
    alternates: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _upc_catalog_match(session: Session, barcode: str | None) -> P100CatalogMatch | None:
    if not barcode:
        return None
    normalized = normalize_upc(barcode)
    if not normalized or not upc_check_digit_valid(normalized):
        return None
    row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if row is None or row.issue_id is None:
        return None
    identity = load_catalog_issue_identity(session, int(row.issue_id))
    if identity is None:
        return None
    return P100CatalogMatch(
        matched=True,
        catalog_issue_id=int(row.issue_id),
        method="upc",
        confidence=0.98,
        series=identity.series,
        issue_number=identity.issue_number,
        publisher=identity.publisher,
        cover_image_url=identity.cover_image_url,
    )


def match_gpt_read_to_catalog(
    session: Session,
    gpt: GptComicReadResult,
    *,
    extracted_barcode: str | None = None,
) -> P100CatalogMatch:
    barcode = extracted_barcode or (gpt.barcode or "").strip() or None
    upc_hit = _upc_catalog_match(session, barcode)
    if upc_hit is not None:
        logger.info(
            "p100.gpt_catalog_match.upc catalog_issue_id=%s barcode=%s",
            upc_hit.catalog_issue_id,
            barcode,
        )
        return upc_hit

    if not (gpt.series or "").strip():
        return P100CatalogMatch()

    candidates = search_catalog_candidates(
        session,
        series=gpt.series,
        issue_number=gpt.issue_number,
        publisher=gpt.publisher,
        year=gpt.year or None,
        issue_title=gpt.issue_title or None,
        limit=8,
    )
    if not candidates:
        logger.info("p100.gpt_catalog_match.none series=%r issue=%r", gpt.series, gpt.issue_number)
        return P100CatalogMatch()

    top = candidates[0]
    alternates = [
        {
            "catalog_issue_id": c.catalog_issue_id,
            "series": c.series,
            "issue_number": c.issue_number,
            "publisher": c.publisher,
            "cover_image_url": c.cover_image_url,
            "confidence": c.confidence,
        }
        for c in candidates[1:6]
    ]
    logger.info(
        "p100.gpt_catalog_match.text catalog_issue_id=%s confidence=%s",
        top.catalog_issue_id,
        top.confidence,
    )
    return P100CatalogMatch(
        matched=True,
        catalog_issue_id=top.catalog_issue_id,
        method="text",
        confidence=float(top.confidence),
        series=top.series,
        issue_number=top.issue_number,
        publisher=top.publisher,
        cover_image_url=top.cover_image_url,
        alternates=alternates,
    )
