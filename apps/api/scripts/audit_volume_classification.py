"""Audit: 'Vol' / 'Volume' text vs collected-edition vs single-issue classification (read-only)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

WATCH_PUBLISHERS = frozenset({"image", "image comics"})
WATCH_SERIES_TOKENS = (
    "youngblood",
    "savage dragon",
    "spawn",
    "witchblade",
)
MILESTONE_ISSUES = {100, 200, 300}


def _numeric_issue(issue_number: str | None) -> float | None:
    if not issue_number:
        return None
    raw = issue_number.strip().lstrip("#").lower()
    m = re.match(r"^(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _vol_in_text(*parts: str | None) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return bool(
        re.search(r"\bvol\.?\s*\d", blob)
        or re.search(r"\bvolume\s+\d", blob)
        or re.search(r"\bvol\s+\d", blob)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Volume / collected-edition classification audit.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1
    host = re.search(r"@([^:/]+)", database_url)
    host_val = host.group(1).lower() if host else ""
    if args.production and host_val in {"localhost", "127.0.0.1"}:
        print("error: production mode requires non-localhost DATABASE_URL", file=sys.stderr)
        return 1

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    scripts_dir = os.path.join(ROOT, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from sqlalchemy import func, or_
    from sqlmodel import Session, select

    from app.db.session import get_engine
    from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
    from app.services.recommendation_catalog_quality import (
        _COLLECTED_EDITION_PATTERNS,
        _matches_any,
        classify_catalog_text,
    )
    from app.services.recommendation_forward_window import iter_forward_release_rows
    from app.services.recommendation_signal_bucket_diagnostic import classify_catalog_product_format
    from owner_lookup import resolve_owner_user_id

    def _blob(series_name: str, title: str, issue_number: str) -> str:
        return f"{series_name} {title} {issue_number}".lower()

    with Session(get_engine()) as session:
        owner_user_id = resolve_owner_user_id(session, args.email)

        stmt = (
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .where(
                or_(
                    func.lower(ReleaseSeries.series_name).contains("vol"),
                    func.lower(ReleaseIssue.title).contains("vol"),
                    func.lower(ReleaseIssue.title).contains("volume"),
                )
            )
        )
        rows = list(session.exec(stmt).all())

        forward_ids = {
            int(issue.id)
            for issue, _ in iter_forward_release_rows(session, owner_user_id=owner_user_id)
            if issue.id is not None
        }

        audited: list[dict] = []
        for issue, series in rows:
            blob = _blob(series.series_name, issue.title or "", issue.issue_number or "")
            quality = classify_catalog_text(
                series_name=series.series_name,
                issue_number=issue.issue_number,
                title=issue.title,
                publisher=series.publisher,
            )
            product_format = classify_catalog_product_format(issue, series)
            num = _numeric_issue(issue.issue_number)
            vol_pattern = _matches_any(blob, _COLLECTED_EDITION_PATTERNS)
            is_collected = quality.is_collected_edition or quality.recommendation_exclusion_reason == "collected_edition"
            is_single = quality.is_single_issue
            is_book = quality.is_book_or_trade

            misclassified_candidate = (
                num is not None
                and num > 0
                and is_collected
                and not is_book
                and vol_pattern
            )
            true_tp_hc = is_book and not is_single

            pub_lower = (series.publisher or "").strip().lower()
            series_lower = (series.series_name or "").lower()
            flags: list[str] = []
            if any(t in series_lower for t in WATCH_SERIES_TOKENS):
                flags.append("watch_series")
            if pub_lower in WATCH_PUBLISHERS or "image" in pub_lower:
                flags.append("image_publisher")
            if num is not None and int(num) in MILESTONE_ISSUES:
                flags.append(f"milestone_{int(num)}")

            audited.append(
                {
                    "issue_id": issue.id,
                    "publisher": series.publisher,
                    "series_name": series.series_name,
                    "issue_number": issue.issue_number,
                    "issue_title": issue.title,
                    "numeric_issue": num,
                    "product_format": product_format,
                    "is_single_issue": is_single,
                    "is_collected_edition": is_collected,
                    "is_book_or_trade": is_book,
                    "exclusion_reason": quality.recommendation_exclusion_reason,
                    "vol_pattern_in_text": vol_pattern,
                    "misclassified_candidate": misclassified_candidate,
                    "true_tp_hc": true_tp_hc,
                    "in_forward_window": int(issue.id or 0) in forward_ids,
                    "flags": flags,
                }
            )

        count_single = sum(1 for r in audited if r["is_single_issue"])
        count_collected = sum(1 for r in audited if r["is_collected_edition"])
        count_book = sum(1 for r in audited if r["is_book_or_trade"])

        misclassified = [r for r in audited if r["misclassified_candidate"]]
        misclassified.sort(
            key=lambda r: (
                0 if r["flags"] else 1,
                -(r["numeric_issue"] or 0),
                r["series_name"] or "",
            )
        )

        true_tp = [r for r in audited if r["true_tp_hc"]][:50]

        impact_forward = sum(1 for r in misclassified if r["in_forward_window"])
        impact_total_misclassified = len(misclassified)

        watch_hits = [r for r in audited if r["flags"]][:80]
        milestone_hits = [
            r
            for r in audited
            if r["numeric_issue"] is not None and int(r["numeric_issue"]) in MILESTONE_ISSUES
        ][:80]

        report = {
            "audit": "volume_classification",
            "owner_user_id": owner_user_id,
            "email": args.email,
            "rows_matching_vol_volume_filter": len(audited),
            "counts": {
                "classified_single_issue": count_single,
                "classified_collected_edition": count_collected,
                "classified_book_or_trade": count_book,
                "misclassified_candidates_numeric_issue_collected": impact_total_misclassified,
                "misclassified_in_forward_window": impact_forward,
            },
            "section_A_true_tp_hc_sample": true_tp[:30],
            "section_B_likely_misclassified_top_100": misclassified[:100],
            "section_C_recommendation_impact_estimate": {
                "description": (
                    "Rows with numeric issue #, vol/volume pattern, collected_edition classification, "
                    "not book/trade — excluded from top recommendations via collected_edition hard exclude."
                ),
                "misclassified_candidate_count": impact_total_misclassified,
                "in_forward_recommendation_window": impact_forward,
                "pct_of_vol_filter_rows": round(
                    100.0 * impact_total_misclassified / max(len(audited), 1),
                    2,
                ),
            },
            "watchlist_youngblood_spawn_dragon_witchblade_image": watch_hits,
            "milestone_issues_100_200_300": milestone_hits,
            "notes": [
                "Collected edition is triggered when series/title/issue blob matches volume/vol N patterns in recommendation_catalog_quality.",
                "Numeric issue numbers (e.g. 100) can still be classified collected if 'Vol 6' appears in series or title.",
                "Youngblood #100 without 'Vol' in stored fields classifies as single_issue; Youngblood Vol 6 #100 does not.",
            ],
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
