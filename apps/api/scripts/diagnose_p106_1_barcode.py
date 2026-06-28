"""Replay P106 + P106.1 for a scanned barcode (ops / local GCD required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, create_engine

from app.core.config import get_settings
from app.services.barcode_validation_service import barcode_encoded_issue_number, effective_publisher_for_barcode
from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path
from app.services.p106_1_gcd_non_barcode_recovery_service import (
    IntakeGcdRecoveryHints,
    diagnose_gcd_non_barcode_recovery,
    gather_intake_gcd_recovery_hints,
)
from app.services.p106_barcode_gap_resolver_service import diagnose_barcode_gap


class _Item:
    def __init__(
        self,
        *,
        publisher: str | None,
        series: str | None,
        issue_number: str | None,
        year: str | None,
    ) -> None:
        self.id = 0
        self.matched_publisher = publisher
        self.matched_series = series
        self.matched_issue_number = issue_number
        self.matched_year = year


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose P106 / P106.1 for one barcode")
    parser.add_argument("barcode", help="Normalized scan barcode (17-digit UPC+5)")
    parser.add_argument("--publisher", default=None)
    parser.add_argument("--series", default=None)
    parser.add_argument("--issue", default=None, help="Issue number hint")
    parser.add_argument("--year", default=None)
    parser.add_argument("--image", default=None, help="Cover crop path for fingerprint boost")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    gcd_path = resolve_gcd_path(None)
    cache_path = resolve_cache_path(None)

    encoded = barcode_encoded_issue_number(args.barcode)
    inferred_pub = effective_publisher_for_barcode(args.barcode, None)

    with Session(engine) as session:
        p106 = diagnose_barcode_gap(session, barcode=args.barcode, gcd_path=gcd_path, cache_path=cache_path)
        item = _Item(
            publisher=args.publisher or inferred_pub,
            series=args.series,
            issue_number=args.issue or (str(encoded) if encoded is not None else None),
            year=args.year,
        )
        image_path = Path(args.image) if args.image else None
        hints = gather_intake_gcd_recovery_hints(
            session,
            item=item,
            normalized_barcode=args.barcode,
            image_path=image_path,
            image_bytes=None,
            p105=None,
        )
        p106_1 = diagnose_gcd_non_barcode_recovery(
            session,
            barcode=args.barcode,
            gcd_path=gcd_path,
            cache_path=cache_path,
            hints=hints,
            image_path=image_path,
            prior_diagnosis=p106,
        )

    report = {
        "barcode": args.barcode,
        "encoded_issue_from_supplement": encoded,
        "inferred_publisher_from_prefix": inferred_pub,
        "gcd_path": str(gcd_path),
        "gcd_exists": gcd_path.is_file(),
        "p106": {
            "gcd_match_count": p106.get("gcd_match_count"),
            "status": p106.get("status"),
            "reason": p106.get("reason"),
            "ready_to_auto_import": p106.get("ready_to_auto_import"),
            "gcd_matches": p106.get("gcd_matches"),
        },
        "recovery_hints": {
            "publisher": hints.publisher,
            "series": hints.series,
            "issue_number": hints.issue_number,
            "year": hints.year,
            "ocr_issue_number": hints.ocr_issue_number,
            "ocr_title": hints.ocr_title,
            "ocr_publisher": hints.ocr_publisher,
            "facsimile_or_reprint": hints.facsimile_or_reprint,
        },
        "p106_1_skipped": bool(p106_1.get("p106_1_skipped")),
        "p106_1": {
            "recovery_stage": p106_1.get("recovery_stage"),
            "recovery_reason": p106_1.get("recovery_reason"),
            "recovery_block_reason": p106_1.get("recovery_block_reason"),
            "ready_to_auto_import": p106_1.get("ready_to_auto_import"),
            "status": p106_1.get("status"),
            "reason": p106_1.get("reason"),
            "proposed_action": p106_1.get("proposed_action"),
            "instrumentation": p106_1.get("p106_1_instrumentation"),
        },
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
