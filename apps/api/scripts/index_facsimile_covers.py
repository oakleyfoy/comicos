"""Fingerprint facsimile / reprint catalog covers so they can be matched directly.

Facsimile and reprint editions visually differ from the original printing (they
carry a modern logo box, price, and barcode), so the original-cover fingerprint in
the index is a poor match for a photo of the reprint. This backfill indexes the
facsimile-specific covers we already hold in the catalog so the recovery path can
surface the edition that physically matches the collector's book.

A catalog issue is treated as a facsimile/reprint when its series name or issue
title matches the reprint cue (facsimile, reprint, digest, ashcan, ...). For each
such issue with a ready cover image that lacks a fingerprint row, we compute and
store the fingerprint.

Usage:
    python scripts/index_facsimile_covers.py [--limit N] [--dry-run] [--database-url URL]
"""
from __future__ import annotations

import argparse
import logging
import re

from sqlmodel import Session, create_engine, select

from app.core.config import get_settings
from app.models.catalog_master import (
    CatalogImage,
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogSeries,
)
from app.services.catalog_fingerprint_service import fingerprint_catalog_image

LOGGER = logging.getLogger(__name__)

# Keep in sync with p102_gcd_modern_acquisition_service._REPRINT_DIGEST.
_REPRINT_CUE = re.compile(
    r"(digest|facsimile|reprint|ashcan|preview|sneak\s*peek|newsstand|magazine|annual\b|one\s*shot|one-shot)",
    re.IGNORECASE,
)


def _is_facsimile_text(*parts: str | None) -> bool:
    return any(part and _REPRINT_CUE.search(part) for part in parts)


def find_facsimile_cover_images_missing_fingerprints(
    session: Session,
    *,
    limit: int,
) -> list[CatalogImage]:
    """Ready cover images for facsimile/reprint issues that lack a fingerprint row."""
    rows = session.exec(
        select(CatalogImage, CatalogIssue, CatalogSeries)
        .join(CatalogIssue, CatalogImage.issue_id == CatalogIssue.id)
        .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
        .where(CatalogImage.image_type == "cover")
        .where(CatalogImage.download_status == "ready")
        .where(CatalogImage.local_path.is_not(None))  # type: ignore[union-attr]
    ).all()

    out: list[CatalogImage] = []
    for image, issue, series in rows:
        if not _is_facsimile_text(series.name, issue.title):
            continue
        existing = session.exec(
            select(CatalogImageFingerprint).where(
                CatalogImageFingerprint.image_id == image.id
            )
        ).first()
        if existing is not None:
            continue
        out.append(image)
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Index facsimile/reprint catalog covers")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    database_url = args.database_url or settings.database_url
    engine = create_engine(database_url)

    indexed = 0
    skipped = 0
    with Session(engine, expire_on_commit=False) as session:
        images = find_facsimile_cover_images_missing_fingerprints(session, limit=args.limit)
        LOGGER.info("facsimile covers missing fingerprints: %s", len(images))
        for image in images:
            row = fingerprint_catalog_image(session, image.id, dry_run=args.dry_run)
            if row is None:
                skipped += 1
                LOGGER.warning("skipped image_id=%s (no resolvable local path)", image.id)
                continue
            indexed += 1
            LOGGER.info(
                "fingerprinted image_id=%s issue_id=%s phash=%s%s",
                image.id,
                image.issue_id,
                row.phash,
                " (dry-run)" if args.dry_run else "",
            )
        if not args.dry_run:
            session.commit()

    LOGGER.info("done indexed=%s skipped=%s dry_run=%s", indexed, skipped, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
