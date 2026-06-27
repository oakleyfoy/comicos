"""Attach a full UPC+5 to a catalog issue (catalog_upc + learned barcode)."""

from __future__ import annotations

import argparse
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p105_barcode_repair_service import (  # noqa: E402
    BarcodeAttachConflict,
    BarcodeAttachError,
    attach_barcode_to_catalog_issue,
    preview_barcode_attach,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach a full comic UPC+5 to a catalog issue.")
    parser.add_argument("--barcode", required=True, help="Full normalized UPC+5 (17 digits)")
    parser.add_argument("--catalog-issue-id", type=int, required=True)
    parser.add_argument("--variant-id", type=int, default=None)
    parser.add_argument(
        "--catalog-upc-source",
        default="manual",
        choices=("manual", "learned"),
        help="catalog_upc.source value when inserting",
    )
    parser.add_argument(
        "--learned-source",
        default="manual",
        help="comic_issue_barcodes.source (default manual)",
    )
    parser.add_argument(
        "--also-learned",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Upsert comic_issue_barcodes (default true)",
    )
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument(
        "--confirm",
        default="",
        help='Must be YES to write (dry-run preview otherwise)',
    )
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine) as session:
        try:
            preview = preview_barcode_attach(
                session,
                barcode=args.barcode,
                catalog_issue_id=args.catalog_issue_id,
                variant_id=args.variant_id,
            )
        except (BarcodeAttachError, BarcodeAttachConflict) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        print("Resolved target:")
        print(f"  series: {preview.series}")
        print(f"  issue: #{preview.issue_number}")
        print(f"  publisher: {preview.publisher or '(unknown)'}")
        print(f"  catalog_issue_id: {preview.catalog_issue_id}")
        print(f"  normalized_barcode: {preview.normalized_barcode}")
        print(f"  validation: {preview.validation_status} — {preview.validation_detail}")
        print(f"  will_insert_catalog_upc: {preview.will_create_catalog_upc}")
        print(f"  will_insert_learned: {preview.will_create_learned}")

        if args.confirm.strip().upper() != "YES":
            print("\nDry run only. Re-run with --confirm YES to write.")
            return 0

        try:
            result = attach_barcode_to_catalog_issue(
                session,
                barcode=args.barcode,
                catalog_issue_id=args.catalog_issue_id,
                variant_id=args.variant_id,
                learned_source=args.learned_source if args.also_learned else "manual",
                catalog_upc_source=args.catalog_upc_source,
                require_catalog_validation=True,
            )
        except (BarcodeAttachError, BarcodeAttachConflict) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        session.commit()
        print("\nWrote:")
        print(f"  catalog_upc_id: {result.catalog_upc_id} (created={result.catalog_upc_created})")
        print(f"  learned_barcode_id: {result.learned_barcode_id} (created={result.learned_created})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
