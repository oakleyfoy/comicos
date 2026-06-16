"""Read-only audit: why core ComicVine runs are or are not on the P97 import queue.

Usage:
  python scripts/p97_core_run_audit.py
  python scripts/p97_core_run_audit.py --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.services.p97_core_run_registry import (  # noqa: E402
    CORE_RUN_REPORT_LABELS,
    expected_publisher_for_report_label,
    pick_best_universe_match,
)
from app.services.p97_comicvine_universe_analytics_service import (  # noqa: E402
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.p97_targeted_core_discovery import find_universe_matches_for_label  # noqa: E402
from app.services.p97_queue_rebalance_service import REBALANCE_STATUSES  # noqa: E402
from app.services.p97_volume_issue_import_queue_service import STATUS_COMPLETE  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

AUDIT_CORE_TITLES = CORE_RUN_REPORT_LABELS


@dataclass(frozen=True)
class CoreRunAuditRow:
    audit_title: str
    expected_publisher: str
    volume_id: int | None
    volume_name: str | None
    publisher: str | None
    publisher_match: bool
    cv_issues: int
    catalog_issues: int
    missing_issues: int
    in_universe: bool
    in_queue: bool
    queue_status: str | None
    eligible_for_rebalance: bool
    queued_label: str
    not_queued_reason: str
    alternate_volume_count: int


def _explain_not_queued(
    *,
    in_universe: bool,
    cv_issues: int,
    missing: int,
    queue_row: P97VolumeIssueImportQueue | None,
) -> str:
    if not in_universe:
        return "Not present in comicvine_volume_universe (volume never discovered)."
    if cv_issues <= 0:
        return (
            "Present in comicvine_volume_universe but count_of_issues is 0 "
            "(nothing to import)."
        )
    if missing <= 0:
        return (
            "Catalog coverage complete (missing=0). Queue build skips volumes with "
            "no gaps and may remove pending queue rows."
        )
    if queue_row is None:
        return (
            "Has missing issues but no p97_volume_issue_import_queue row — "
            "import queue has not been built/updated since discovery."
        )
    status = (queue_row.status or "").strip().lower()
    if status == STATUS_COMPLETE:
        return (
            "Queue row exists with status=complete (not in pending/running/failed "
            "eligible set)."
        )
    if status not in REBALANCE_STATUSES:
        return f"Queue row status={status!r} (outside eligible rebalance statuses)."
    return "Eligible for import queue ordering."


def build_core_run_audit(session: Session) -> list[CoreRunAuditRow]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    queue_by_volume = {
        int(row.comicvine_volume_id): row
        for row in session.exec(select(P97VolumeIssueImportQueue)).all()
    }
    indexes = build_catalog_coverage_indexes(session)

    rows: list[CoreRunAuditRow] = []
    for audit_title in AUDIT_CORE_TITLES:
        expected_pub = expected_publisher_for_report_label(audit_title)
        candidates = find_universe_matches_for_label(universes, audit_title)
        primary, pub_ok = pick_best_universe_match(
            candidates,
            audit_title,
            name_getter=lambda u: u.name,
            publisher_getter=lambda u: u.publisher,
            issue_count_getter=lambda u: u.count_of_issues,
            start_year_getter=lambda u: u.start_year,
        )
        alternates = max(0, len(candidates) - (1 if primary else 0))

        if primary is None:
            rows.append(
                CoreRunAuditRow(
                    audit_title=audit_title,
                    expected_publisher=expected_pub,
                    volume_id=None,
                    volume_name=None,
                    publisher=None,
                    publisher_match=False,
                    cv_issues=0,
                    catalog_issues=0,
                    missing_issues=0,
                    in_universe=False,
                    in_queue=False,
                    queue_status=None,
                    eligible_for_rebalance=False,
                    queued_label="NO",
                    not_queued_reason=_explain_not_queued(
                        in_universe=False,
                        cv_issues=0,
                        missing=0,
                        queue_row=None,
                    ),
                    alternate_volume_count=0,
                )
            )
            continue

        if not pub_ok:
            reason_prefix = (
                f"No {expected_pub} volume in universe; best title match is "
                f"{primary.publisher!r}. "
            )
        else:
            reason_prefix = ""

        volume_id = int(primary.volume_id)
        cv_issues = int(primary.count_of_issues or 0)
        catalog = existing_issue_count_for_volume(
            volume_id=volume_id,
            name=primary.name,
            publisher=primary.publisher,
            indexes=indexes,
        )
        missing = max(cv_issues - catalog, 0)
        queue_row = queue_by_volume.get(volume_id)
        in_queue = queue_row is not None
        queue_status = queue_row.status if queue_row else None
        eligible = (
            in_queue
            and queue_status in REBALANCE_STATUSES
            and missing > 0
        )
        reason = reason_prefix + _explain_not_queued(
            in_universe=True,
            cv_issues=cv_issues,
            missing=missing,
            queue_row=queue_row,
        )
        queued_label = "YES" if eligible else "NO"
        rows.append(
            CoreRunAuditRow(
                audit_title=audit_title,
                expected_publisher=expected_pub,
                volume_id=volume_id,
                volume_name=primary.name,
                publisher=primary.publisher,
                publisher_match=pub_ok,
                cv_issues=cv_issues,
                catalog_issues=catalog,
                missing_issues=missing,
                in_universe=True,
                in_queue=in_queue,
                queue_status=queue_status,
                eligible_for_rebalance=eligible,
                queued_label=queued_label,
                not_queued_reason=reason,
                alternate_volume_count=alternates,
            )
        )
    return rows


def format_audit_report(rows: list[CoreRunAuditRow]) -> str:
    lines = ["CORE RUN AUDIT", ""]
    total_missing = 0
    total_queued_missing = 0
    total_not_queued_missing = 0

    for row in rows:
        lines.append(row.audit_title)
        lines.append(f"  Expected publisher: {row.expected_publisher}")
        lines.append(f"  Publisher match: {'YES' if row.publisher_match else 'NO'}")
        if row.volume_name and row.volume_name != row.audit_title:
            lines.append(f"  Matched volume: {row.volume_name}")
        if row.volume_id is not None:
            lines.append(f"  Volume ID: {row.volume_id}")
        if row.publisher:
            lines.append(f"  Publisher: {row.publisher}")
        lines.append(f"  CV Issues: {row.cv_issues:,}")
        lines.append(f"  Catalog: {row.catalog_issues:,}")
        lines.append(f"  Missing: {row.missing_issues:,}")
        lines.append(f"  In universe: {'YES' if row.in_universe else 'NO'}")
        lines.append(f"  In import queue: {'YES' if row.in_queue else 'NO'}")
        if row.queue_status:
            lines.append(f"  Queue status: {row.queue_status}")
        lines.append(f"  Eligible (pending/running/failed): {'YES' if row.eligible_for_rebalance else 'NO'}")
        lines.append(f"  Queued: {row.queued_label}")
        lines.append(f"  Why: {row.not_queued_reason}")
        if row.alternate_volume_count:
            lines.append(
                f"  Note: {row.alternate_volume_count} additional core volume(s) "
                f"also match this title."
            )
        lines.append("")

        total_missing += row.missing_issues
        if row.eligible_for_rebalance:
            total_queued_missing += row.missing_issues
        else:
            total_not_queued_missing += row.missing_issues

    lines.extend(
        [
            "SUMMARY",
            f"  Missing issues across all core runs (primary volumes): {total_missing:,}",
            f"  Missing on eligible queue rows: {total_queued_missing:,}",
            f"  Missing not on eligible queue: {total_not_queued_missing:,}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 core run queue presence audit")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine) as session:
        rows = build_core_run_audit(session)

    if args.json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
    else:
        print(format_audit_report(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
