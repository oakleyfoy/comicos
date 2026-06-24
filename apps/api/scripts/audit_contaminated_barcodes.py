"""Audit (and optionally clean) catalog UPC rows that map modern DC/Marvel barcodes to
implausible catalog records (wrong publisher family or pre-1976 era).

ComicOS stores barcodes in ``catalog_upc.normalized_upc`` mapped to ``catalog_issue`` (not a
``comic_issues.barcode`` column). This script applies the same safe-match rules used at lookup
time so the catalog itself cannot resolve, e.g., 761941... -> Harvey / 1952.

Usage:
    python -m scripts.audit_contaminated_barcodes            # report only
    python -m scripts.audit_contaminated_barcodes --delete   # delete contaminated catalog_upc rows
"""

from __future__ import annotations

import argparse

from sqlalchemy import text
from sqlmodel import Session

from app.db.session import get_engine
from app.services.barcode_validation_service import validate_barcode_catalog_match

# Barcodes from the reported incident plus the broader modern-direct-market families.
NEEDLES = ("761941341927", "76194134192", "76194134192703921")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Delete contaminated catalog_upc rows")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        db = session.exec(text("SELECT current_database()")).one()[0]
        print(f"database: {db}")
        print(f"delete mode: {args.delete}")

        rows = session.exec(
            text(
                """
                SELECT u.id            AS upc_id,
                       u.normalized_upc AS upc,
                       u.issue_id      AS issue_id,
                       cs.name         AS series,
                       ci.issue_number AS issue_number,
                       cp.name         AS publisher,
                       EXTRACT(YEAR FROM ci.cover_date)::int AS year
                FROM catalog_upc u
                LEFT JOIN catalog_issue ci   ON ci.id = u.issue_id
                LEFT JOIN catalog_series cs  ON cs.id = ci.series_id
                LEFT JOIN catalog_publisher cp ON cp.id = COALESCE(ci.publisher_id, cs.publisher_id)
                WHERE u.normalized_upc LIKE '761941%'
                   OR u.normalized_upc LIKE '759606%'
                """
            )
        ).all()

        print(f"\nmodern direct-market catalog_upc rows: {len(rows)}")
        contaminated: list[int] = []
        for row in rows:
            m = row._mapping
            verdict = validate_barcode_catalog_match(
                str(m["upc"]),
                publisher=m["publisher"],
                issue_number=str(m["issue_number"]) if m["issue_number"] is not None else None,
                year=str(m["year"]) if m["year"] is not None else None,
            )
            flag = "OK" if verdict.status == "exact_match" else "CONTAMINATED"
            print(
                f"  [{flag}] upc_id={m['upc_id']} upc={m['upc']} "
                f"publisher={m['publisher']!r} series={m['series']!r} "
                f"issue={m['issue_number']!r} year={m['year']!r}"
            )
            if verdict.status != "exact_match":
                print(f"           reason: {verdict.reason}")
                contaminated.append(int(m["upc_id"]))

        # Direct needle search across the incident barcodes.
        for needle in NEEDLES:
            hits = session.exec(
                text("SELECT id, normalized_upc, issue_id FROM catalog_upc WHERE normalized_upc LIKE :p"),
                params={"p": f"%{needle}%"},
            ).all()
            print(f"\nneedle {needle}: {len(hits)} catalog_upc hits")
            for h in hits:
                print(f"  {dict(h._mapping)}")

        print(f"\ncontaminated catalog_upc rows: {len(contaminated)} -> {contaminated}")
        if contaminated and args.delete:
            session.exec(
                text("DELETE FROM catalog_upc WHERE id = ANY(:ids)"),
                params={"ids": contaminated},
            )
            session.commit()
            print(f"deleted {len(contaminated)} contaminated rows")
        elif contaminated:
            print("re-run with --delete to remove these rows")


if __name__ == "__main__":
    main()
