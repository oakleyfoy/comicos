"""P98 — Major publisher completeness report (read-only)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_major_publisher_completeness_service import (  # noqa: E402
    OPTIONAL_PUBLISHERS,
    REQUIRED_PUBLISHERS,
    build_major_publisher_completeness_report,
    default_report_path,
    save_major_publisher_completeness_report,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _print_publisher(metrics) -> None:
    _log(f"Publisher: {metrics.publisher}")
    _log(f"  CV Volumes:              {metrics.comicvine_universe_volumes:,}")
    _log(f"  Canonical P98 Volumes:   {metrics.canonical_p98_volumes:,}")
    _log(f"  Foreign Superseded:      {metrics.superseded_foreign_volumes:,}")
    _log(f"  CV without P98 volume:   {metrics.cv_volumes_without_canonical_p98:,}")
    _log(f"  Discoverable Issues:     {metrics.discoverable_issues:,}")
    _log(f"  Issue Shells Built:        {metrics.issue_shells_built:,}")
    _log(f"  Missing Issue Shells:    {metrics.missing_issue_shells:,}")
    _log(f"  Queued Missing Issues:   {metrics.queued_missing_issues:,}")
    _log(f"  Catalog Issues:          {metrics.catalog_issue_count:,}")
    _log(f"  Import Gap (shells-catalog): {metrics.import_gap_issues:,}")
    _log(f"  Coverage:                {metrics.coverage_percent}%")
    if metrics.top_missing_volumes:
        _log("  Top missing volumes:")
        for row in metrics.top_missing_volumes[:25]:
            suffix = "" if row.has_canonical_p98_volume else " [NO P98 VOLUME]"
            _log(
                f"    {row.volume_name[:44]:<44} missing={row.missing_count:>6} "
                f"(disc={row.discoverable_issues}, shells={row.issue_shells}){suffix}"
            )
    _log("")


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 major publisher completeness report")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--no-optional", action="store_true")
    parser.add_argument("--output", type=str, default=None, help="Override report JSON path")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        report = build_major_publisher_completeness_report(
            session,
            include_optional=not args.no_optional,
            top_missing_per_publisher=args.top,
        )

    out_path = save_major_publisher_completeness_report(
        report,
        path=__import__("pathlib").Path(args.output) if args.output else None,
    )

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Report written: {out_path}")
    _log("")
    _log("Targets: " + ", ".join(REQUIRED_PUBLISHERS))
    if not args.no_optional:
        _log("Optional: " + ", ".join(OPTIONAL_PUBLISHERS))
    _log("")

    for metrics in report.publishers:
        _print_publisher(metrics)

    g = report.global_summary
    _log("GLOBAL UNIVERSE SUMMARY")
    _log(f"  Publishers:           {g.publishers:,}")
    _log(f"  Volumes:              {g.volumes:,}")
    _log(f"  Discoverable Issues:  {g.discoverable_issues:,}")
    _log(f"  Issue Shells:         {g.issue_shells:,}")
    _log(f"  Missing Shells:       {g.missing_issue_shells:,}")
    _log(f"  Coverage:             {g.coverage_percent}%")
    _log(f"  Catalog Issues:       {g.catalog_issue_count:,}")
    _log(f"  Import Gap:           {g.import_gap_issues:,}")
    _log("")
    _log("Gap interpretation (major publishers):")
    gi = g.gap_interpretation
    _log(f"  Missing volume rows (CV without P98): {gi['missing_volume_rows_major_publishers']:,}")
    _log(f"  Missing issue shells:               {gi['missing_issue_shells_major_publishers']:,}")
    _log(f"  Import gap (shells not in catalog):   {gi['import_gap_from_shells_major_publishers']:,}")
    _log("")
    _log("Answers:")
    _log("  1. Marvel completeness: see Marvel coverage % and missing shells above.")
    _log("  2. DC completeness: see DC Comics coverage % above.")
    _log("  3. IDW completeness: see IDW Publishing coverage % above.")
    _log(f"  4. Missing issue shells (global): {g.missing_issue_shells:,}")
    _log(
        "  5. Major publishers: almost all CV volumes have P98 rows; remaining major gap is "
        f"{gi['missing_issue_shells_major_publishers']:,} missing shells vs "
        f"{gi['missing_volume_rows_major_publishers']:,} undiscovered P98 volume rows. "
        f"Global missing shells ({g.missing_issue_shells:,}) includes non-major / long-tail publishers."
    )
    _log(
        "  6. More ComicVine volume discovery is low priority for Marvel/DC/Boom/Dark Horse; "
        "focus shell expansion and catalog import on existing CV volumes first."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
