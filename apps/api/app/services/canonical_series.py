import re
from datetime import date

from sqlalchemy import extract, func
from sqlmodel import Session, select

from app.models import CanonicalSeries, InventoryCopy
from app.models.asset_ledger import utc_now
from app.schemas.ops import OpsCanonicalSeriesRow
from app.services.metadata_audits import record_metadata_audit


def _normalize_series_component(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compute_series_key(publisher: str, canonical_title: str) -> str:
    normalized_publisher = _normalize_series_component(publisher)
    normalized_title = _normalize_series_component(canonical_title)
    return f"{normalized_publisher}|{normalized_title}"


def get_or_create_canonical_series(
    session: Session,
    *,
    publisher: str,
    canonical_title: str,
    actor_user_id: int | None = None,
    audit_reason: str | None = None,
) -> CanonicalSeries:
    normalized_publisher = _normalize_series_component(publisher)
    normalized_title = _normalize_series_component(canonical_title)
    series_key = compute_series_key(normalized_publisher, normalized_title)
    existing = session.exec(
        select(CanonicalSeries).where(CanonicalSeries.series_key == series_key)
    ).first()
    now = utc_now()

    if existing is not None:
        existing.last_seen_at = now
        existing.updated_at = now
        session.add(existing)
        session.flush()
        return existing

    canonical_series = CanonicalSeries(
        canonical_title=normalized_title,
        canonical_publisher=normalized_publisher,
        series_key=series_key,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        is_active=True,
    )
    session.add(canonical_series)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="canonical_series",
        entity_id=canonical_series.id,
        action="enriched",
        after_snapshot=canonical_series,
        reason=audit_reason,
        actor_user_id=actor_user_id,
    )
    return canonical_series


def update_canonical_series_release_window(
    canonical_series: CanonicalSeries,
    *,
    release_date: date | None,
) -> CanonicalSeries:
    if release_date is None:
        return canonical_series

    if (
        canonical_series.earliest_known_release_date is None
        or release_date < canonical_series.earliest_known_release_date
    ):
        canonical_series.earliest_known_release_date = release_date
    if (
        canonical_series.latest_known_release_date is None
        or release_date > canonical_series.latest_known_release_date
    ):
        canonical_series.latest_known_release_date = release_date

    canonical_series.updated_at = utc_now()
    return canonical_series


def list_canonical_series_registry(
    session: Session,
    *,
    publisher: str | None = None,
    title: str | None = None,
    earliest_release_year_min: int | None = None,
    earliest_release_year_max: int | None = None,
    latest_release_year_min: int | None = None,
    latest_release_year_max: int | None = None,
) -> list[OpsCanonicalSeriesRow]:
    publisher_filter = publisher.strip() if publisher else ""
    title_filter = title.strip() if title else ""
    stmt = (
        select(
            CanonicalSeries.id.label("id"),
            CanonicalSeries.canonical_title.label("canonical_title"),
            CanonicalSeries.canonical_publisher.label("canonical_publisher"),
            CanonicalSeries.series_key.label("series_key"),
            CanonicalSeries.first_seen_at.label("first_seen_at"),
            CanonicalSeries.last_seen_at.label("last_seen_at"),
            CanonicalSeries.earliest_known_release_date.label("earliest_known_release_date"),
            CanonicalSeries.latest_known_release_date.label("latest_known_release_date"),
            CanonicalSeries.created_at.label("created_at"),
            CanonicalSeries.updated_at.label("updated_at"),
            CanonicalSeries.is_active.label("is_active"),
            func.count(InventoryCopy.id).label("inventory_count"),
        )
        .select_from(CanonicalSeries)
        .join(
            InventoryCopy,
            InventoryCopy.canonical_series_id == CanonicalSeries.id,
            isouter=True,
        )
        .group_by(
            CanonicalSeries.id,
            CanonicalSeries.canonical_title,
            CanonicalSeries.canonical_publisher,
            CanonicalSeries.series_key,
            CanonicalSeries.first_seen_at,
            CanonicalSeries.last_seen_at,
            CanonicalSeries.earliest_known_release_date,
            CanonicalSeries.latest_known_release_date,
            CanonicalSeries.created_at,
            CanonicalSeries.updated_at,
            CanonicalSeries.is_active,
        )
        .order_by(
            CanonicalSeries.canonical_publisher.asc(),
            CanonicalSeries.canonical_title.asc(),
            CanonicalSeries.id.asc(),
        )
    )

    if publisher_filter:
        stmt = stmt.where(CanonicalSeries.canonical_publisher.ilike(f"%{publisher_filter}%"))
    if title_filter:
        stmt = stmt.where(CanonicalSeries.canonical_title.ilike(f"%{title_filter}%"))

    earliest_date = CanonicalSeries.earliest_known_release_date
    if earliest_release_year_min is not None:
        stmt = stmt.where(
            earliest_date.is_not(None),
            extract("year", earliest_date) >= earliest_release_year_min,
        )
    if earliest_release_year_max is not None:
        stmt = stmt.where(
            earliest_date.is_not(None),
            extract("year", earliest_date) <= earliest_release_year_max,
        )

    latest_date = CanonicalSeries.latest_known_release_date
    if latest_release_year_min is not None:
        stmt = stmt.where(
            latest_date.is_not(None),
            extract("year", latest_date) >= latest_release_year_min,
        )
    if latest_release_year_max is not None:
        stmt = stmt.where(
            latest_date.is_not(None),
            extract("year", latest_date) <= latest_release_year_max,
        )

    rows = session.exec(stmt).all()
    return [OpsCanonicalSeriesRow.model_validate(row._mapping) for row in rows]
