from __future__ import annotations

from sqlmodel import Session, select

from app.models.purchase_variant import PurchaseVariantRecommendation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.purchase_variant import PurchaseVariantRecommendationRead
from app.services.purchase_variant_engine import generate_variant_recommendations


def _variant_key(release_id: int, variant_id: int | None) -> tuple[int, int | None]:
    return (release_id, variant_id)


def _latest_variant_rows(session: Session, *, owner_user_id: int) -> dict[tuple[int, int | None], PurchaseVariantRecommendation]:
    rows = session.exec(
        select(PurchaseVariantRecommendation)
        .where(PurchaseVariantRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseVariantRecommendation.created_at.desc(), PurchaseVariantRecommendation.id.desc())
    ).all()
    latest: dict[tuple[int, int | None], PurchaseVariantRecommendation] = {}
    for row in rows:
        key = _variant_key(int(row.release_id), row.variant_id)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(session: Session, *, row: PurchaseVariantRecommendation) -> PurchaseVariantRecommendationRead:
    issue = session.get(ReleaseIssue, row.release_id)
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    return PurchaseVariantRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        release_id=int(row.release_id),
        variant_id=row.variant_id,
        cover_label=row.cover_label,
        variant_type=row.variant_type,  # type: ignore[arg-type]
        recommendation=row.recommendation,  # type: ignore[arg-type]
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        title=issue.title if issue else "",
        issue_number=issue.issue_number if issue else "",
        publisher=series.publisher if series else "",
        series_name=series.series_name if series else "",
    )


def generate_purchase_variants(session: Session, *, owner_user_id: int) -> int:
    computed = generate_variant_recommendations(session, owner_user_id=owner_user_id)
    latest = _latest_variant_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        key = _variant_key(result.release_id, result.variant_id)
        prior = latest.get(key)
        if prior is not None:
            if (
                prior.recommendation == result.recommendation
                and prior.rationale == result.rationale
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
            ):
                continue
        session.add(
            PurchaseVariantRecommendation(
                owner_user_id=owner_user_id,
                release_id=result.release_id,
                variant_id=result.variant_id,
                cover_label=result.cover_label,
                variant_type=result.variant_type,
                recommendation=result.recommendation,
                confidence_score=result.confidence_score,
                rationale=result.rationale,
            )
        )
        created += 1
    session.commit()
    return created


def list_purchase_variant_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    variant_type: str | None = None,
    publisher: str | None = None,
    release_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseVariantRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_variant_rows(session, owner_user_id=owner_user_id)
    items: list[PurchaseVariantRecommendationRead] = []
    for key in sorted(latest.keys()):
        row = latest[key]
        if release_id is not None and row.release_id != int(release_id):
            continue
        if recommendation and row.recommendation != recommendation.strip().upper():
            continue
        if variant_type and row.variant_type != variant_type.strip().upper():
            continue
        read = _to_read(session, row=row)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.confidence_score, r.release_id, r.id))
    total = len(items)
    return items[offset : offset + limit], total


def list_latest_purchase_variant_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    variant_type: str | None = None,
    publisher: str | None = None,
    release_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseVariantRecommendationRead], int]:
    return list_purchase_variant_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation=recommendation,
        variant_type=variant_type,
        publisher=publisher,
        release_id=release_id,
        limit=limit,
        offset=offset,
    )


def get_purchase_variant_recommendation(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> PurchaseVariantRecommendationRead:
    row = session.get(PurchaseVariantRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Purchase variant recommendation not found.")
    return _to_read(session, row=row)
