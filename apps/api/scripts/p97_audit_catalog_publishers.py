from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.services.catalog_import_quality_service import score_import_candidate  # noqa: E402
from app.services.catalog_publisher_registry import (  # noqa: E402
    is_international_publisher,
    is_primary_us_publisher,
)


def _audit_csv_path() -> Path:
    settings = get_settings()
    root = Path(settings.catalog_storage_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    out_dir = root / "p97"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "catalog_international_audit.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 catalog publisher quality audit (report only; no deletes)")
    args = parser.parse_args()
    _ = args

    primary_counts: dict[str, int] = defaultdict(int)
    international_counts: dict[str, int] = defaultdict(int)
    publisher_issue_counts: dict[str, int] = defaultdict(int)
    quality_summary = {"PRIMARY": 0, "ACCEPTABLE": 0, "LOW_PRIORITY": 0, "REJECTED": 0}
    international_publisher_count = 0
    international_series_count = 0
    international_issue_count = 0
    csv_rows: list[dict[str, str | int]] = []
    seen_international_series: set[int] = set()

    with Session(get_engine()) as session:
        publishers = session.exec(select(CatalogPublisher)).all()
        pub_by_id = {int(p.id or 0): p for p in publishers if p.id is not None}

        for pub in publishers:
            name = pub.name or "Unknown"
            issue_count = session.exec(
                select(CatalogIssue).where(CatalogIssue.publisher_id == pub.id)
            ).all()
            icount = len(issue_count)
            if icount == 0:
                continue
            publisher_issue_counts[name] = icount
            quality = score_import_candidate(publisher=name, series_name=None)
            quality_summary[quality.quality_tier] = quality_summary.get(quality.quality_tier, 0) + 1
            if is_primary_us_publisher(name):
                primary_counts[name] = icount
            if is_international_publisher(name):
                international_counts[name] = icount
                international_publisher_count += 1

        series_rows = session.exec(select(CatalogSeries)).all()
        for series in series_rows:
            pub = pub_by_id.get(int(series.publisher_id or 0))
            pub_name = pub.name if pub else "Unknown"
            if not is_international_publisher(pub_name):
                continue
            sid = int(series.id or 0)
            issue_count = len(
                session.exec(select(CatalogIssue).where(CatalogIssue.series_id == series.id)).all()
            )
            if issue_count == 0:
                continue
            if sid not in seen_international_series:
                seen_international_series.add(sid)
                international_series_count += 1
            international_issue_count += issue_count
            quality = score_import_candidate(publisher=pub_name, series_name=series.name)
            country_guess = "International"
            csv_rows.append(
                {
                    "publisher": pub_name,
                    "series": series.name or "",
                    "issue_count": issue_count,
                    "country_guess": country_guess,
                    "quality_score": quality.quality_score,
                }
            )

    print("Primary publishers:")
    for name in sorted(primary_counts.keys()):
        print(f"  {name}: {primary_counts[name]}")
    print("\nInternational publishers:")
    for name in sorted(international_counts.keys()):
        print(f"  {name}: {international_counts[name]}")
    print("\nTop 50 publishers by issue count:")
    for name, count in sorted(publisher_issue_counts.items(), key=lambda x: (-x[1], x[0]))[:50]:
        print(f"  {name}: {count}")
    print("\nQuality summary (publishers with issues):")
    print(json.dumps(quality_summary, indent=2))
    print("\nExisting catalog international audit (report only):")
    print(f"  international_publisher_count={international_publisher_count}")
    print(f"  international_series_count={international_series_count}")
    print(f"  international_issue_count={international_issue_count}")

    csv_path = _audit_csv_path()
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["publisher", "series", "issue_count", "country_guess", "quality_score"],
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\nWrote {csv_path} ({len(csv_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
