"""P97 known-good volume queue — read-only yield analytics and forecasting."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue
from app.models.catalog_p97 import P97ComicVineVolumeQueue
from app.schemas.p97_volume_analytics import (
    FinalCatalogProjection,
    PublisherYieldRow,
    QueueForecastRow,
    VolumeAnalyticsSummary,
    VolumeYieldRow,
)
from app.services.p97_volume_queue_service import (
    STATUS_FAILED,
    STATUS_IMPORTED,
    STATUS_IMPORTING,
    STATUS_PENDING,
    STATUS_THROTTLED,
    issues_per_api_request,
)

PENDING_FORECAST_STATUSES = (STATUS_PENDING, STATUS_IMPORTING, STATUS_THROTTLED)


def _publisher_label(publisher: str | None) -> str:
    text = (publisher or "").strip()
    return text or "Unknown"


def _current_catalog_size(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(CatalogIssue)).one())


def _imported_rows(session: Session) -> list[P97ComicVineVolumeQueue]:
    return list(
        session.exec(
            select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.status == STATUS_IMPORTED)
        ).all()
    )


def _row_to_yield(row: P97ComicVineVolumeQueue) -> VolumeYieldRow:
    created = int(row.issues_created or 0)
    updated = int(row.issues_updated or 0)
    requests = int(row.api_requests_used or 0)
    return VolumeYieldRow(
        volume_id=int(row.comicvine_volume_id),
        series_name=row.series_name,
        publisher=row.publisher,
        status=row.status,
        issues_created=created,
        issues_updated=updated,
        api_requests_used=requests,
        issues_per_request=issues_per_api_request(created, requests),
        created_at=row.created_at,
        completed_at=row.last_imported_at,
    )


def _global_avg_issues_per_imported_volume(session: Session) -> float:
    imported = _imported_rows(session)
    if not imported:
        return 0.0
    total_created = sum(int(r.issues_created or 0) for r in imported)
    return float(total_created) / float(len(imported))


def _publisher_avg_issues_per_volume(session: Session) -> dict[str, float]:
    imported = _imported_rows(session)
    by_pub: dict[str, list[int]] = {}
    for row in imported:
        key = _publisher_label(row.publisher)
        by_pub.setdefault(key, []).append(int(row.issues_created or 0))
    return {
        pub: (sum(values) / len(values) if values else 0.0)
        for pub, values in by_pub.items()
    }


def _estimate_for_pending(
    row: P97ComicVineVolumeQueue,
    *,
    publisher_avg: dict[str, float],
    global_avg: float,
) -> int:
    key = _publisher_label(row.publisher)
    avg = publisher_avg.get(key)
    if avg is None or avg <= 0:
        avg = global_avg
    return max(0, int(round(avg)))


def _projected_remaining_issues(session: Session) -> int:
    publisher_avg = _publisher_avg_issues_per_volume(session)
    global_avg = _global_avg_issues_per_imported_volume(session)
    pending = session.exec(
        select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.status.in_(PENDING_FORECAST_STATUSES))
    ).all()
    return sum(
        _estimate_for_pending(row, publisher_avg=publisher_avg, global_avg=global_avg) for row in pending
    )


def get_volume_summary(session: Session) -> VolumeAnalyticsSummary:
    counts = session.exec(
        select(P97ComicVineVolumeQueue.status, func.count()).group_by(P97ComicVineVolumeQueue.status)
    ).all()
    status_counts = {str(status): int(count) for status, count in counts}
    total_volumes = sum(status_counts.values())

    imported_volumes = status_counts.get(STATUS_IMPORTED, 0)
    pending_volumes = sum(status_counts.get(s, 0) for s in PENDING_FORECAST_STATUSES)
    failed_volumes = status_counts.get(STATUS_FAILED, 0)

    totals = session.exec(
        select(
            func.coalesce(func.sum(P97ComicVineVolumeQueue.issues_created), 0),
            func.coalesce(func.sum(P97ComicVineVolumeQueue.issues_updated), 0),
            func.coalesce(func.sum(P97ComicVineVolumeQueue.api_requests_used), 0),
        )
    ).one()
    issues_created = int(totals[0])
    issues_updated = int(totals[1])
    api_requests = int(totals[2])

    avg_issues_per_volume = (
        round(issues_created / float(imported_volumes), 1) if imported_volumes else 0.0
    )
    avg_issues_per_request = (
        round(issues_created / float(api_requests), 1) if api_requests else 0.0
    )

    current_catalog = _current_catalog_size(session)
    projected_remaining = _projected_remaining_issues(session)

    return VolumeAnalyticsSummary(
        total_volumes=total_volumes,
        imported_volumes=imported_volumes,
        pending_volumes=pending_volumes,
        failed_volumes=failed_volumes,
        issues_created=issues_created,
        issues_updated=issues_updated,
        avg_issues_per_volume=avg_issues_per_volume,
        avg_issues_per_request=avg_issues_per_request,
        current_catalog_size=current_catalog,
        projected_remaining_issues=projected_remaining,
        projected_final_catalog_size=current_catalog + projected_remaining,
    )


def get_top_created_volumes(session: Session, *, limit: int = 100) -> list[VolumeYieldRow]:
    rows = session.exec(
        select(P97ComicVineVolumeQueue)
        .where(P97ComicVineVolumeQueue.status == STATUS_IMPORTED)
        .order_by(P97ComicVineVolumeQueue.issues_created.desc(), P97ComicVineVolumeQueue.comicvine_volume_id.asc())
        .limit(limit)
    ).all()
    return [_row_to_yield(row) for row in rows]


def get_top_updated_volumes(session: Session, *, limit: int = 100) -> list[VolumeYieldRow]:
    rows = session.exec(
        select(P97ComicVineVolumeQueue)
        .where(P97ComicVineVolumeQueue.status == STATUS_IMPORTED)
        .order_by(P97ComicVineVolumeQueue.issues_updated.desc(), P97ComicVineVolumeQueue.comicvine_volume_id.asc())
        .limit(limit)
    ).all()
    return [_row_to_yield(row) for row in rows]


def get_publisher_yields(session: Session) -> list[PublisherYieldRow]:
    imported = _imported_rows(session)
    grouped: dict[str, dict[str, int | float]] = {}
    for row in imported:
        key = _publisher_label(row.publisher)
        bucket = grouped.setdefault(
            key,
            {"volume_count": 0, "issues_created": 0, "issues_updated": 0, "api_requests": 0},
        )
        bucket["volume_count"] = int(bucket["volume_count"]) + 1
        bucket["issues_created"] = int(bucket["issues_created"]) + int(row.issues_created or 0)
        bucket["issues_updated"] = int(bucket["issues_updated"]) + int(row.issues_updated or 0)
        bucket["api_requests"] = int(bucket["api_requests"]) + int(row.api_requests_used or 0)

    out: list[PublisherYieldRow] = []
    for publisher, bucket in grouped.items():
        volume_count = int(bucket["volume_count"])
        created = int(bucket["issues_created"])
        updated = int(bucket["issues_updated"])
        requests = int(bucket["api_requests"])
        avg_vol = round(created / volume_count, 1) if volume_count else 0.0
        avg_req_vol = round(requests / volume_count, 1) if volume_count else 0.0
        avg_ipr = round(created / requests, 1) if requests else 0.0
        out.append(
            PublisherYieldRow(
                publisher=publisher,
                volume_count=volume_count,
                issues_created=created,
                issues_updated=updated,
                avg_issues_per_volume=avg_vol,
                avg_created_per_volume=avg_vol,
                avg_requests_per_volume=avg_req_vol,
                avg_issues_per_request=avg_ipr,
            )
        )
    out.sort(key=lambda r: (-r.issues_created, r.publisher))
    return out


def get_remaining_queue_forecast(session: Session) -> list[QueueForecastRow]:
    publisher_avg = _publisher_avg_issues_per_volume(session)
    global_avg = _global_avg_issues_per_imported_volume(session)
    rows = session.exec(
        select(P97ComicVineVolumeQueue)
        .where(P97ComicVineVolumeQueue.status.in_(PENDING_FORECAST_STATUSES))
        .order_by(P97ComicVineVolumeQueue.priority.asc(), P97ComicVineVolumeQueue.comicvine_volume_id.asc())
    ).all()
    forecast = [
        QueueForecastRow(
            volume_id=int(row.comicvine_volume_id),
            series_name=row.series_name,
            publisher=row.publisher,
            status=row.status,
            estimated_remaining_issues=_estimate_for_pending(
                row, publisher_avg=publisher_avg, global_avg=global_avg
            ),
        )
        for row in rows
    ]
    forecast.sort(key=lambda r: (-r.estimated_remaining_issues, r.volume_id))
    return forecast


def get_projected_final_catalog_size(session: Session) -> FinalCatalogProjection:
    current = _current_catalog_size(session)
    remaining = _projected_remaining_issues(session)
    return FinalCatalogProjection(
        current_catalog_size=current,
        projected_remaining_issues=remaining,
        projected_final_catalog_size=current + remaining,
    )
