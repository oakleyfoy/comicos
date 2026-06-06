"""P74-03 release recommendation outcome tracking."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.models.p74_foc_purchase import P74PurchaseRecommendation
from app.models.p74_release_analytics import P74ReleaseOutcome
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.schemas.release_analytics import P74ReleaseOutcomeRead
from app.services.purchase_priority_score import P74_ACTION_PASS, P74_ACTION_WATCH

OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_PARTIAL = "PARTIAL"
OUTCOME_FAILURE = "FAILURE"
OUTCOME_PENDING = "PENDING"


def _derive_status(
    *,
    purchase_action: str,
    recommended: int,
    purchased: int,
) -> str:
    if purchase_action in {P74_ACTION_PASS, P74_ACTION_WATCH} and purchased == 0:
        return OUTCOME_SUCCESS
    if recommended <= 0 and purchased == 0:
        return OUTCOME_SUCCESS
    if purchased >= recommended:
        return OUTCOME_SUCCESS
    if purchased > 0 and purchased < recommended:
        return OUTCOME_PARTIAL
    if recommended > 0 and purchased == 0:
        return OUTCOME_FAILURE
    return OUTCOME_PENDING


def _estimate_roi(priority_score: int, purchased: int, recommended: int) -> tuple[float, Decimal]:
    if purchased <= 0:
        return 0.0, Decimal("0")
    base = float(priority_score) * 0.4
    fill = min(1.0, purchased / max(recommended, 1))
    roi = round(base * fill, 1)
    profit = Decimal(str(round(roi * purchased * 2.5, 2)))
    return roi, profit


def sync_release_outcomes_from_recommendations(session: Session, *, owner_user_id: int) -> list[P74ReleaseOutcome]:
    recs = session.exec(
        select(P74PurchaseRecommendation)
        .where(P74PurchaseRecommendation.owner_user_id == owner_user_id)
        .order_by(P74PurchaseRecommendation.generated_at.desc(), P74PurchaseRecommendation.id.desc())
    ).all()
    latest: dict[int, P74PurchaseRecommendation] = {}
    for rec in recs:
        rid = int(rec.release_issue_id)
        if rid not in latest:
            latest[rid] = rec

    outcomes: list[P74ReleaseOutcome] = []
    for rid, rec in latest.items():
        purchased = max(rec.ordered_quantity, rec.owned_quantity)
        if rec.purchase_action not in {P74_ACTION_PASS} and rec.quantity_recommended > 0:
            purchased = max(purchased, min(rec.quantity_recommended, rec.ordered_quantity or rec.quantity_recommended))
        roi, profit = _estimate_roi(rec.priority_score, purchased, rec.quantity_recommended)
        status = _derive_status(
            purchase_action=rec.purchase_action,
            recommended=rec.quantity_recommended,
            purchased=purchased,
        )
        existing = session.exec(
            select(P74ReleaseOutcome)
            .where(P74ReleaseOutcome.owner_user_id == owner_user_id)
            .where(P74ReleaseOutcome.release_issue_id == rid)
            .order_by(P74ReleaseOutcome.recorded_at.desc())
            .limit(1)
        ).first()
        row = P74ReleaseOutcome(
            owner_user_id=owner_user_id,
            release_issue_id=rid,
            recommended_quantity=rec.quantity_recommended,
            ordered_quantity=rec.ordered_quantity,
            actual_quantity_purchased=purchased,
            foc_date=rec.foc_date,
            release_date=rec.release_date,
            market_performance_pct=roi,
            inventory_performance_pct=round(roi * 0.85, 1),
            actual_profit=profit,
            actual_roi_pct=roi,
            outcome_status=status,
            purchase_action=rec.purchase_action,
            metadata_json={"priority_score": rec.priority_score},
        )
        if existing is None or existing.outcome_status != status or existing.actual_quantity_purchased != purchased:
            session.add(row)
            outcomes.append(row)
    session.commit()
    return outcomes


def list_release_outcomes(session: Session, *, owner_user_id: int, limit: int = 100) -> list[P74ReleaseOutcomeRead]:
    sync_release_outcomes_from_recommendations(session, owner_user_id=owner_user_id)
    rows = session.exec(
        select(P74ReleaseOutcome)
        .where(P74ReleaseOutcome.owner_user_id == owner_user_id)
        .order_by(P74ReleaseOutcome.recorded_at.desc(), P74ReleaseOutcome.id.desc())
        .limit(limit)
    ).all()
    return [P74ReleaseOutcomeRead.model_validate(r) for r in rows]


def _category_keys_for_issue(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> list[str]:
    keys: list[str] = []
    num = issue.issue_number.strip().lstrip("#")
    if num == "1":
        keys.append("NUMBER_ONE")
    variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == int(issue.id or 0))).all()
    if variants:
        keys.append("VARIANT")
    if any(v.ratio_value for v in variants):
        keys.append("RATIO_VARIANT")
    signals = session.exec(
        select(ReleaseKeySignal)
        .where(ReleaseKeySignal.owner_user_id == owner_user_id)
        .where(ReleaseKeySignal.issue_id == int(issue.id or 0))
    ).all()
    for s in signals:
        st = s.signal_type.upper()
        if "FIRST" in st:
            keys.append("FIRST_APPEARANCE")
        if "KEY" in st:
            keys.append("MILESTONE_ISSUE")
        if "CREATOR" in st:
            keys.append("CREATOR_EVENT")
    if series.series_type.upper() in {"NEW", "ONGOING"} and num == "1":
        keys.append("PUBLISHER_LAUNCH")
    if not keys:
        keys.append("SERIES_RELAUNCH")
    return keys
