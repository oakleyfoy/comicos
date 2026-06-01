from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.collected_run import COLLECTED_RUN_STATUSES
from app.models.release_intelligence import ReleaseSeries
from app.services.metadata_enrichment import normalize_series_title_with_aliases
from app.services.run_detection import parse_issue_number_for_run_detection, run_detection_groups_for_user

RECENT_OWNERSHIP_DAYS = 365
RELEASE_ENDED_STATUSES = frozenset({"ENDED", "COMPLETE", "COMPLETED", "CANCELLED", "FINISHED"})


@dataclass(frozen=True)
class CollectedRunCandidate:
    publisher: str
    series_name: str
    latest_owned_issue: str
    total_owned_issues: int
    run_status: str


def _run_identity_key(*, publisher: str, series_name: str) -> tuple[str, str]:
    return (
        publisher.strip().lower(),
        series_name.strip().lower(),
    )


def _latest_owned_issue_label(owned_issue_numbers: list[str]) -> str:
    if not owned_issue_numbers:
        return ""
    parsed = sorted(
        (parse_issue_number_for_run_detection(label) for label in owned_issue_numbers),
        key=lambda item: item.sortable_key,
    )
    return parsed[-1].display_value or parsed[-1].raw_value


def _release_series_status_map(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], str]:
    rows = session.exec(select(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_user_id)).all()
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        key = _run_identity_key(publisher=row.publisher, series_name=row.series_name)
        out[key] = str(row.status or "").strip().upper()
    return out


def _inventory_activity_at(
    session: Session,
    *,
    inventory_copy_ids: list[int],
) -> datetime | None:
    if not inventory_copy_ids:
        return None
    rows = session.exec(select(InventoryCopy).where(InventoryCopy.id.in_(inventory_copy_ids))).all()
    latest: datetime | None = None
    for row in rows:
        candidate = row.received_at or row.created_at
        if candidate is None:
            continue
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def _series_is_ended(*, release_status: str | None, series_status: str) -> bool:
    _ = series_status
    return bool(release_status and release_status in RELEASE_ENDED_STATUSES)


def determine_run_status(
    *,
    release_status: str | None,
    series_status: str,
    last_activity_at: datetime | None,
    total_owned_issues: int,
    now: datetime | None = None,
) -> str:
    if total_owned_issues <= 0:
        return "UNKNOWN"
    if _series_is_ended(release_status=release_status, series_status=series_status):
        return "COMPLETE"
    if last_activity_at is None:
        return "UNKNOWN"
    reference = now or datetime.now(timezone.utc)
    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)
    if reference - last_activity_at <= timedelta(days=RECENT_OWNERSHIP_DAYS):
        return "ACTIVE"
    return "INACTIVE"


def generate_collected_runs(session: Session, *, owner_user_id: int) -> list[CollectedRunCandidate]:
    """Read-only detection from inventory grouping and release intelligence metadata."""
    groups = run_detection_groups_for_user(session, owner_user_id=owner_user_id)
    release_status_by_series = _release_series_status_map(session, owner_user_id=owner_user_id)
    candidates: list[CollectedRunCandidate] = []

    for group in groups:
        normalized_title = (
            normalize_series_title_with_aliases(group.title, session=session).canonical_value or group.title
        ).strip()
        publisher = group.publisher.strip()
        identity = _run_identity_key(publisher=publisher, series_name=normalized_title)
        release_status = release_status_by_series.get(identity)
        if release_status is None:
            release_status = release_status_by_series.get(_run_identity_key(publisher=publisher, series_name=group.title.strip()))

        last_activity = _inventory_activity_at(session, inventory_copy_ids=group.inventory_copy_ids)
        status = determine_run_status(
            release_status=release_status,
            series_status=group.series_status,
            last_activity_at=last_activity,
            total_owned_issues=group.distinct_issue_count,
        )
        if status not in COLLECTED_RUN_STATUSES:
            status = "UNKNOWN"

        candidates.append(
            CollectedRunCandidate(
                publisher=publisher,
                series_name=normalized_title,
                latest_owned_issue=_latest_owned_issue_label(group.owned_issue_numbers),
                total_owned_issues=int(group.distinct_issue_count),
                run_status=status,
            )
        )

    candidates.sort(key=lambda item: (item.publisher.lower(), item.series_name.lower()))
    return candidates
