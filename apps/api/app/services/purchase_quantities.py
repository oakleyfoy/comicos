from __future__ import annotations

from sqlmodel import Session, select

from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.pull_list import PullListDecision
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.purchase_quantity import PurchaseQuantityRecommendationRead
from app.services.purchase_quantity_engine import generate_quantity_recommendations
from app.services.recommendation_v2_engine import _latest_scores_by_issue


def _latest_pull_decisions(session: Session, *, owner_user_id: int) -> dict[int, PullListDecision]:
    rows = session.exec(
        select(PullListDecision)
        .where(PullListDecision.owner_user_id == owner_user_id)
        .order_by(PullListDecision.created_at.desc(), PullListDecision.id.desc())
    ).all()
    latest: dict[int, PullListDecision] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _latest_quantity_rows(session: Session, *, owner_user_id: int) -> dict[int, PurchaseQuantityRecommendation]:
    rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseQuantityRecommendation.created_at.desc(), PurchaseQuantityRecommendation.id.desc())
    ).all()
    latest: dict[int, PurchaseQuantityRecommendation] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _to_read(
    session: Session,
    *,
    row: PurchaseQuantityRecommendation,
    pull_decision: str | None,
) -> PurchaseQuantityRecommendationRead:
    issue = session.get(ReleaseIssue, row.release_id)
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    return PurchaseQuantityRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        release_id=int(row.release_id),
        recommendation_tier=row.recommendation_tier,  # type: ignore[arg-type]
        quantity_recommended=int(row.quantity_recommended),
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        title=issue.title if issue else "",
        issue_number=issue.issue_number if issue else "",
        publisher=series.publisher if series else "",
        series_name=series.series_name if series else "",
        pull_list_decision=pull_decision,
    )


def _pull_decisions_by_release(session: Session, *, owner_user_id: int) -> dict[int, PullListDecision]:
    return _latest_pull_decisions(session, owner_user_id=owner_user_id)


def generate_purchase_quantities(session: Session, *, owner_user_id: int) -> int:
    """Append-only persistence; skip when latest row matches computed output."""
    v2_by_issue = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    pull_by_release = _pull_decisions_by_release(session, owner_user_id=owner_user_id)
    computed = generate_quantity_recommendations(
        session,
        owner_user_id=owner_user_id,
        v2_by_issue=v2_by_issue,
        pull_by_release=pull_by_release,
    )
    latest = _latest_quantity_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.release_id)
        if prior is not None:
            if (
                prior.recommendation_tier == result.recommendation_tier
                and prior.quantity_recommended == result.quantity_recommended
                and prior.rationale == result.rationale
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
            ):
                continue
        session.add(
            PurchaseQuantityRecommendation(
                owner_user_id=owner_user_id,
                release_id=result.release_id,
                recommendation_tier=result.recommendation_tier,
                quantity_recommended=result.quantity_recommended,
                confidence_score=result.confidence_score,
                rationale=result.rationale,
            )
        )
        created += 1
    session.commit()
    return created


def list_purchase_quantity_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    tier: str | None = None,
    quantity: int | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseQuantityRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    pull_by_release = _pull_decisions_by_release(session, owner_user_id=owner_user_id)
    latest = _latest_quantity_rows(session, owner_user_id=owner_user_id)
    items: list[PurchaseQuantityRecommendationRead] = []
    for release_id in sorted(latest.keys()):
        row = latest[release_id]
        if tier and row.recommendation_tier != tier.strip().upper():
            continue
        if quantity is not None and row.quantity_recommended != int(quantity):
            continue
        pull = pull_by_release.get(release_id)
        read = _to_read(session, row=row, pull_decision=pull.decision_type if pull else None)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.confidence_score, r.release_id))
    total = len(items)
    return items[offset : offset + limit], total


def list_latest_purchase_quantity_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    tier: str | None = None,
    quantity: int | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseQuantityRecommendationRead], int]:
    return list_purchase_quantity_recommendations(
        session,
        owner_user_id=owner_user_id,
        tier=tier,
        quantity=quantity,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def get_purchase_quantity_recommendation(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> PurchaseQuantityRecommendationRead:
    row = session.get(PurchaseQuantityRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Purchase quantity recommendation not found.")
    pull = _pull_decisions_by_release(session, owner_user_id=owner_user_id).get(row.release_id)
    return _to_read(session, row=row, pull_decision=pull.decision_type if pull else None)
