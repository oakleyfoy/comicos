"""Read-only audit: Youngblood release feed coverage (no rebuild, no scoring changes)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SEARCH_TERMS = (
    "youngblood",
    "youngblood vol 6",
    "youngblood #100",
    "youngblood 100",
    "youngblood vol. 6",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    scripts_dir = os.path.join(ROOT, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from sqlalchemy import func, or_
    from sqlmodel import Session, select

    from app.db.session import get_engine
    from app.models.lunar_feed import LunarFeedRawRow
    from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
    from app.services.recommendation_catalog_quality import classify_catalog_text
    from app.services.recommendation_signal_bucket_diagnostic import classify_catalog_product_format
    from owner_lookup import resolve_owner_user_id

    def _blob(*parts: str) -> str:
        return " ".join(p for p in parts if p).lower()

    def _matches_any(text: str) -> list[str]:
        t = text.lower()
        return [term for term in SEARCH_TERMS if term in t or (term.replace(" ", "") in t.replace(" ", ""))]

    with Session(get_engine()) as session:
        owner_user_id = resolve_owner_user_id(session, args.email)

        raw_hits: list[dict] = []
        raw_rows = session.exec(select(LunarFeedRawRow).limit(50000)).all()
        for row in raw_rows:
            payload = row.row_payload_json or {}
            parts = [
                str(payload.get(k, ""))
                for k in (
                    "Title",
                    "ProductName",
                    "FULL_TITLE",
                    "full_title",
                    "title",
                    "SeriesName",
                    "MainDesc",
                    "Series Name",
                    "Series",
                    "series_name",
                    "IssueNumber",
                    "Issue Number",
                    "issue_number",
                    "PublisherName",
                    "Publisher",
                )
            ]
            text = _blob(*parts)
            matched = _matches_any(text)
            if not matched:
                continue
            if "100" not in text and "#100" not in text and " vol 6" not in text and "vol. 6" not in text:
                if "youngblood" in text and any(x in text for x in ("#100", " 100", "vol 6", "vol. 6")):
                    pass
                elif "youngblood" in text:
                    continue
            raw_hits.append(
                {
                    "source": "lunar_feed_raw_row",
                    "feed_run_id": row.feed_run_id,
                    "row_index": row.row_index,
                    "product_code": row.product_code,
                    "matched_terms": matched,
                    "title": payload.get("Title") or payload.get("ProductName") or payload.get("FULL_TITLE"),
                    "series": payload.get("SeriesName") or payload.get("MainDesc") or payload.get("Series"),
                    "issue_number_field": payload.get("IssueNumber") or payload.get("Issue Number"),
                    "publisher": payload.get("PublisherName") or payload.get("Publisher"),
                }
            )

        catalog_hits: list[dict] = []
        stmt = (
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .where(
                or_(
                    func.lower(ReleaseSeries.series_name).contains("youngblood"),
                    func.lower(ReleaseIssue.title).contains("youngblood"),
                )
            )
        )
        for issue, series in session.exec(stmt).all():
            text = _blob(series.series_name, issue.title, issue.issue_number, series.publisher)
            matched = _matches_any(text)
            quality = classify_catalog_text(
                series_name=series.series_name,
                issue_number=issue.issue_number,
                title=issue.title,
                publisher=series.publisher,
            )
            product_format = classify_catalog_product_format(issue, series)
            catalog_hits.append(
                {
                    "source": "release_issue",
                    "issue_id": issue.id,
                    "release_uuid": issue.release_uuid,
                    "series_name": series.series_name,
                    "issue_number": issue.issue_number,
                    "issue_title": issue.title,
                    "publisher": series.publisher,
                    "release_status": issue.release_status,
                    "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
                    "matched_terms": matched,
                    "catalog_quality": {
                        "is_single_issue": quality.is_single_issue,
                        "recommendation_exclusion_reason": quality.recommendation_exclusion_reason,
                    },
                    "product_format_diagnostic": product_format,
                    "usable_single_issue": product_format in ("single_issue", "variant"),
                }
            )

        target_rows = [
            r
            for r in catalog_hits
            if "100" in (r.get("issue_number") or "")
            or "100" in (r.get("issue_title") or "").lower()
            or "vol 6" in (r.get("issue_title") or "").lower()
            or "vol. 6" in (r.get("issue_title") or "").lower()
        ]
        raw_target = [
            r
            for r in raw_hits
            if r.get("issue_number_field") == "100"
            or "100" in (r.get("title") or "").lower()
            or "vol 6" in (r.get("title") or "").lower()
            or "vol. 6" in (r.get("title") or "").lower()
        ]

        classification = "A"
        notes: list[str] = []
        if raw_target:
            classification = "B_or_D"
            notes.append("Raw lunar rows exist for Youngblood + vol6/#100-shaped text.")
        elif raw_hits:
            notes.append("Youngblood appears in raw feed but no vol6/#100-shaped row in scanned lunar raw sample.")
        if target_rows:
            unusable = [r for r in target_rows if not r["usable_single_issue"]]
            if unusable:
                classification = "C"
                notes.append(
                    "Normalized ReleaseIssue exists but classified as non-single-issue "
                    f"({unusable[0].get('product_format_diagnostic')}; "
                    f"exclusion={unusable[0]['catalog_quality'].get('recommendation_exclusion_reason')})."
                )
            else:
                classification = "D"
                notes.append("Usable single-issue row exists under unexpected title/key.")
        elif catalog_hits and not target_rows:
            if not raw_target:
                classification = "A"
                notes.append("No catalog row matching Youngblood Vol 6 #100; other Youngblood rows may exist.")
        if not raw_hits and not catalog_hits:
            classification = "A"
            notes.append("No Youngblood in lunar raw scan (limit 50k) or owner catalog.")

        report = {
            "audit": "release_feed_youngblood_vol6_100",
            "owner_user_id": owner_user_id,
            "classification": classification,
            "classification_legend": {
                "A": "absent from source feed / not imported to catalog",
                "B": "present in raw feed but filtered out before ReleaseIssue",
                "C": "present but classified as TP/book/collected edition",
                "D": "present but normalized under unexpected title",
            },
            "notes": notes,
            "raw_lunar_rows_matching_youngblood": len(raw_hits),
            "raw_lunar_rows_vol6_or_100": raw_target[:40],
            "release_issue_rows_matching_youngblood": len(catalog_hits),
            "release_issue_rows_vol6_or_100": target_rows[:40],
            "all_catalog_youngblood_sample": catalog_hits[:25],
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
