"""P97 volume yield analytics report (read-only).

Usage:
  python scripts/p97_volume_yield_report.py
  python scripts/p97_volume_yield_report.py --top 100
  python scripts/p97_volume_yield_report.py --publishers
  python scripts/p97_volume_yield_report.py --remaining
  python scripts/p97_volume_yield_report.py --projection
"""

from __future__ import annotations

import argparse
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services import p97_volume_analytics_service as analytics  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_float(value: float) -> str:
    return f"{value:,.1f}"


def _leader_line(label: str, value: str, *, width: int = 52) -> str:
    dots = max(1, width - len(label) - len(value))
    return f"{label}{'.' * dots}{value}"


def _series_label(name: str | None, volume_id: int) -> str:
    text = (name or f"Volume {volume_id}").strip()
    return text[:26]


def format_summary_report(session: Session, *, top_limit: int = 25) -> str:
    summary = analytics.get_volume_summary(session)
    top_created = analytics.get_top_created_volumes(session, limit=top_limit)
    top_publishers = analytics.get_publisher_yields(session)[:top_limit]

    lines = [
        "P97 VOLUME ANALYTICS",
        "",
        f"Imported Volumes: {_fmt_int(summary.imported_volumes)}",
        f"Pending Volumes: {_fmt_int(summary.pending_volumes)}",
        "",
        f"Issues Created: {_fmt_int(summary.issues_created)}",
        f"Issues Updated: {_fmt_int(summary.issues_updated)}",
        "",
        f"Avg Issues/Volume: {_fmt_float(summary.avg_issues_per_volume)}",
        f"Avg Issues/API Request: {_fmt_float(summary.avg_issues_per_request)}",
        "",
        f"Current Catalog: {_fmt_int(summary.current_catalog_size)}",
        "",
        f"Projected Remaining: {_fmt_int(summary.projected_remaining_issues)}",
        "",
        f"Projected Final Catalog: {_fmt_int(summary.projected_final_catalog_size)}",
        "",
        "TOP CREATED VOLUMES",
        "",
    ]
    for row in top_created:
        label = _series_label(row.series_name, row.volume_id)
        lines.append(_leader_line(label, _fmt_int(row.issues_created)))
    lines.extend(["", "TOP PUBLISHERS", ""])
    for row in top_publishers:
        lines.append(_leader_line(row.publisher[:26], _fmt_int(row.issues_created)))
    return "\n".join(lines)


def format_top_created(session: Session, *, limit: int) -> str:
    rows = analytics.get_top_created_volumes(session, limit=limit)
    lines = ["TOP CREATED VOLUMES", ""]
    for row in rows:
        label = _series_label(row.series_name, row.volume_id)
        lines.append(_leader_line(label, _fmt_int(row.issues_created)))
    return "\n".join(lines)


def format_publishers(session: Session) -> str:
    rows = analytics.get_publisher_yields(session)
    lines = ["TOP PUBLISHERS", ""]
    for row in rows:
        lines.append(_leader_line(row.publisher[:26], _fmt_int(row.issues_created)))
    return "\n".join(lines)


def format_remaining(session: Session, *, limit: int = 50) -> str:
    rows = analytics.get_remaining_queue_forecast(session)[:limit]
    total = analytics.get_volume_summary(session).projected_remaining_issues
    lines = [
        "REMAINING QUEUE FORECAST",
        "",
        f"Projected Remaining (total): {_fmt_int(total)}",
        "",
    ]
    for row in rows:
        label = _series_label(row.series_name, row.volume_id)
        lines.append(_leader_line(label, _fmt_int(row.estimated_remaining_issues)))
    return "\n".join(lines)


def format_projection(session: Session) -> str:
    proj = analytics.get_projected_final_catalog_size(session)
    lines = [
        "FINAL CATALOG PROJECTION",
        "",
        f"Current Catalog Size: {_fmt_int(proj.current_catalog_size)}",
        f"Projected Remaining Issues: {_fmt_int(proj.projected_remaining_issues)}",
        f"Projected Final Catalog Size: {_fmt_int(proj.projected_final_catalog_size)}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 volume yield analytics (read-only)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--top", type=int, metavar="N", help="Show top N created volumes only")
    parser.add_argument("--publishers", action="store_true", help="Publisher yield report")
    parser.add_argument("--remaining", action="store_true", help="Remaining queue forecast")
    parser.add_argument("--projection", action="store_true", help="Final catalog projection")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            if args.projection:
                text = format_projection(session)
            elif args.remaining:
                text = format_remaining(session)
            elif args.publishers:
                text = format_publishers(session)
            elif args.top is not None:
                text = format_top_created(session, limit=args.top)
            else:
                text = format_summary_report(session, top_limit=25)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
