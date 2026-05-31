from __future__ import annotations

from sqlmodel import Session, select

from app.models.portfolio_rebalancing import PortfolioRebalanceRecommendation
from app.schemas.portfolio_rebalancing import PortfolioRebalanceRecommendationRead, PortfolioRebalanceSummaryRead
from app.services.portfolio_rebalancing_engine import generate_portfolio_rebalancing_recommendations


def _latest_rows(session: Session, *, owner_user_id: int) -> dict[tuple[str, str], PortfolioRebalanceRecommendation]:
    rows = session.exec(
        select(PortfolioRebalanceRecommendation)
        .where(PortfolioRebalanceRecommendation.owner_user_id == owner_user_id)
        .order_by(PortfolioRebalanceRecommendation.created_at.desc(), PortfolioRebalanceRecommendation.id.desc())
    ).all()
    latest: dict[tuple[str, str], PortfolioRebalanceRecommendation] = {}
    for row in rows:
        key = (row.rebalance_type, row.target_key)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: PortfolioRebalanceRecommendation) -> PortfolioRebalanceRecommendationRead:
    pub = ""
    if row.target_key.startswith("publisher:"):
        pub = row.target_label
    elif row.target_key.startswith("title:"):
        inner = row.target_key[6:]
        pub = inner.split("|")[0] if "|" in inner else ""
    return PortfolioRebalanceRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        rebalance_type=row.rebalance_type,  # type: ignore[arg-type]
        target_key=row.target_key,
        target_label=row.target_label,
        exposure_value=float(row.exposure_value),
        exposure_percent=float(row.exposure_percent),
        recommended_action=row.recommended_action,  # type: ignore[arg-type]
        priority_score=float(row.priority_score),
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        publisher=pub,
    )


def persist_portfolio_rebalancing_recommendations(session: Session, *, owner_user_id: int) -> int:
    computed = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_user_id)
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get((result.rebalance_type, result.target_key))
        if prior is not None:
            if (
                abs(float(prior.exposure_value) - float(result.exposure_value)) < 1e-9
                and abs(float(prior.exposure_percent) - float(result.exposure_percent)) < 1e-9
                and prior.recommended_action == result.recommended_action
                and abs(float(prior.priority_score) - float(result.priority_score)) < 1e-9
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
                and prior.rationale == result.rationale
            ):
                continue
        row = PortfolioRebalanceRecommendation(
            owner_user_id=owner_user_id,
            rebalance_type=result.rebalance_type,
            target_key=result.target_key,
            target_label=result.target_label,
            exposure_value=result.exposure_value,
            exposure_percent=result.exposure_percent,
            recommended_action=result.recommended_action,
            priority_score=result.priority_score,
            confidence_score=result.confidence_score,
            rationale=result.rationale,
        )
        session.add(row)
        created += 1
        latest[(result.rebalance_type, result.target_key)] = row
    session.commit()
    return created


def list_portfolio_rebalancing_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    rebalance_type: str | None = None,
    recommended_action: str | None = None,
    priority_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PortfolioRebalanceRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    items: list[PortfolioRebalanceRecommendationRead] = []
    for row in latest.values():
        if rebalance_type and row.rebalance_type != rebalance_type.strip().upper():
            continue
        if recommended_action and row.recommended_action != recommended_action.strip().upper():
            continue
        if priority_min is not None and float(row.priority_score) < float(priority_min):
            continue
        read = _to_read(row)
        if publisher and publisher.strip().lower() not in read.publisher.lower() and publisher.strip().lower() not in row.target_label.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.priority_score, r.rebalance_type, r.target_key))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_portfolio_rebalancing(
    session: Session,
    *,
    owner_user_id: int,
    rebalance_type: str | None = None,
    recommended_action: str | None = None,
    priority_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PortfolioRebalanceRecommendationRead], int]:
    persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_user_id)
    return list_portfolio_rebalancing_recommendations(
        session,
        owner_user_id=owner_user_id,
        rebalance_type=rebalance_type,
        recommended_action=recommended_action,
        priority_min=priority_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_portfolio_rebalancing_summary(session: Session, *, owner_user_id: int) -> PortfolioRebalanceSummaryRead:
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    counts = {"REDUCE_EXPOSURE": 0, "REVIEW_POSITION": 0, "HOLD": 0}
    priority_sum = 0.0
    exposure_sum = 0.0
    for row in latest.values():
        counts[row.recommended_action] = counts.get(row.recommended_action, 0) + 1
        priority_sum += float(row.priority_score)
        exposure_sum += float(row.exposure_value)
    total = len(latest)
    avg = round(priority_sum / total, 1) if total else 0.0
    return PortfolioRebalanceSummaryRead(
        total_recommendations=total,
        reduce_exposure_count=int(counts.get("REDUCE_EXPOSURE", 0)),
        review_position_count=int(counts.get("REVIEW_POSITION", 0)),
        hold_count=int(counts.get("HOLD", 0)),
        average_priority_score=avg,
        total_exposure_value=round(exposure_sum, 2),
    )
