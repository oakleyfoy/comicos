from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.dealer_copilot import (
    DealerCopilotExecution,
    DealerOpportunityScore,
    DealerRecommendation,
    DealerRecommendationEvidence,
    DealerRecommendationReview,
)
from app.models.market_forecast import MarketForecast, MarketRiskAssessment
from app.models.market_intelligence import MarketObservation, MarketSignal
from app.schemas.dealer_copilot import (
    DealerCopilotDashboardRead,
    DealerCopilotExecutionListResponse,
    DealerCopilotExecutionRead,
    DealerCopilotRunResponse,
    DealerCopilotSummaryRead,
    DealerOpportunityScoreListResponse,
    DealerOpportunityScoreRead,
    DealerRecommendationDetail,
    DealerRecommendationEvidenceRead,
    DealerRecommendationListResponse,
    DealerRecommendationRead,
    DealerRecommendationReviewRead,
)
from app.services.agent_registry import clamp_agent_pagination

RECOMMENDATION_STATUS_OPEN = "OPEN"
REVIEW_STATUS_REVIEWED = "REVIEWED"
REVIEW_STATUS_DISMISSED = "DISMISSED"
REVIEW_STATUS_ACCEPTED = "ACCEPTED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def start_execution(session: Session, *, owner_user_id: int, agent_code: str) -> DealerCopilotExecution:
    row = DealerCopilotExecution(
        owner_user_id=owner_user_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def finish_execution(session: Session, *, execution: DealerCopilotExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def _review_rows(session: Session, *, recommendation_id: int) -> list[DealerRecommendationReview]:
    return session.exec(
        select(DealerRecommendationReview)
        .where(DealerRecommendationReview.recommendation_id == recommendation_id)
        .order_by(DealerRecommendationReview.reviewed_at.asc(), DealerRecommendationReview.id.asc())
    ).all()


def _evidence_rows(session: Session, *, recommendation_id: int) -> list[DealerRecommendationEvidence]:
    return session.exec(
        select(DealerRecommendationEvidence)
        .where(DealerRecommendationEvidence.recommendation_id == recommendation_id)
        .order_by(DealerRecommendationEvidence.created_at.asc(), DealerRecommendationEvidence.id.asc())
    ).all()


def _review_read(row: DealerRecommendationReview) -> DealerRecommendationReviewRead:
    return DealerRecommendationReviewRead.model_validate(row)


def _evidence_read(row: DealerRecommendationEvidence) -> DealerRecommendationEvidenceRead:
    return DealerRecommendationEvidenceRead.model_validate(row)


def _display_status(row: DealerRecommendation, reviews: list[DealerRecommendationReview]) -> str:
    if reviews:
        return reviews[-1].review_status
    return row.recommendation_status


def _recommendation_read(session: Session, row: DealerRecommendation) -> DealerRecommendationRead:
    reviews = _review_rows(session, recommendation_id=int(row.id or 0))
    latest = _review_read(reviews[-1]) if reviews else None
    return DealerRecommendationRead(
        id=int(row.id or 0),
        owner_user_id=row.owner_user_id,
        agent_execution_id=row.agent_execution_id,
        recommendation_uuid=row.recommendation_uuid,
        recommendation_type=row.recommendation_type,
        asset_type=row.asset_type,
        asset_id=row.asset_id,
        title=row.title,
        description=row.description,
        confidence_score=row.confidence_score,
        priority_score=row.priority_score,
        recommendation_status=_display_status(row, reviews),
        created_at=row.created_at,
        latest_review=latest,
    )


def _opportunity_read(row: DealerOpportunityScore) -> DealerOpportunityScoreRead:
    return DealerOpportunityScoreRead.model_validate(row)


def _execution_read(row: DealerCopilotExecution) -> DealerCopilotExecutionRead:
    return DealerCopilotExecutionRead.model_validate(row)


def create_recommendation_with_evidence(
    session: Session,
    *,
    owner_user_id: int,
    execution_id: int | None,
    recommendation_key: str,
    recommendation_type: str,
    asset_type: str,
    asset_id: int | None,
    title: str,
    description: str,
    confidence_score: float,
    priority_score: float,
    evidence: list[dict[str, Any]],
) -> DealerRecommendationRead:
    if not evidence:
        raise ValueError("Dealer recommendations require at least one evidence record.")
    row = DealerRecommendation(
        owner_user_id=owner_user_id,
        agent_execution_id=execution_id,
        recommendation_uuid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"dealer-recommendation:{owner_user_id}:{execution_id}:{recommendation_key.strip().lower()}",
            )
        ),
        recommendation_type=recommendation_type.strip().upper(),
        asset_type=asset_type.strip(),
        asset_id=asset_id,
        title=title.strip(),
        description=description.strip(),
        confidence_score=_clamp01(confidence_score),
        priority_score=_clamp01(priority_score),
        recommendation_status=RECOMMENDATION_STATUS_OPEN,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    for item in evidence:
        session.add(
            DealerRecommendationEvidence(
                recommendation_id=int(row.id or 0),
                evidence_type=str(item["evidence_type"]).strip().lower(),
                evidence_source=str(item["evidence_source"]).strip(),
                evidence_payload_json=_json_safe(item.get("evidence_payload_json") or {}),
                evidence_score=_clamp01(float(item.get("evidence_score", 0.0))),
                created_at=utc_now(),
            )
        )
    session.flush()
    return _recommendation_read(session, row)


def _latest_signals_by_asset(session: Session, *, owner_user_id: int) -> dict[tuple[str, int], list[MarketSignal]]:
    rows = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .where(MarketSignal.asset_id.is_not(None))
        .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
    ).all()
    out: dict[tuple[str, int], list[MarketSignal]] = {}
    for row in rows:
        if row.asset_id is None:
            continue
        key = (row.asset_type, int(row.asset_id))
        out.setdefault(key, []).append(row)
    return out


def _latest_forecasts_by_asset(session: Session, *, owner_user_id: int) -> dict[tuple[str, int], list[MarketForecast]]:
    rows = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .where(MarketForecast.asset_id.is_not(None))
        .order_by(MarketForecast.created_at.desc(), MarketForecast.id.desc())
    ).all()
    out: dict[tuple[str, int], list[MarketForecast]] = {}
    for row in rows:
        if row.asset_id is None:
            continue
        key = (row.asset_type, int(row.asset_id))
        out.setdefault(key, []).append(row)
    return out


def _latest_risks_by_asset(session: Session, *, owner_user_id: int) -> dict[tuple[str, int], list[MarketRiskAssessment]]:
    rows = session.exec(
        select(MarketRiskAssessment)
        .where(MarketRiskAssessment.owner_user_id == owner_user_id)
        .where(MarketRiskAssessment.asset_id.is_not(None))
        .order_by(MarketRiskAssessment.created_at.desc(), MarketRiskAssessment.id.desc())
    ).all()
    out: dict[tuple[str, int], list[MarketRiskAssessment]] = {}
    for row in rows:
        if row.asset_id is None:
            continue
        key = (row.asset_type, int(row.asset_id))
        out.setdefault(key, []).append(row)
    return out


def calculate_opportunity_scores(session: Session, *, owner_user_id: int) -> list[DealerOpportunityScoreRead]:
    signals_by_asset = _latest_signals_by_asset(session, owner_user_id=owner_user_id)
    forecasts_by_asset = _latest_forecasts_by_asset(session, owner_user_id=owner_user_id)
    risks_by_asset = _latest_risks_by_asset(session, owner_user_id=owner_user_id)
    keys = sorted({*signals_by_asset.keys(), *forecasts_by_asset.keys(), *risks_by_asset.keys()})
    created: list[DealerOpportunityScore] = []
    for asset_type, asset_id in keys:
        forecasts = forecasts_by_asset.get((asset_type, asset_id), [])
        signals = signals_by_asset.get((asset_type, asset_id), [])
        risks = risks_by_asset.get((asset_type, asset_id), [])

        bullish = any("BULLISH" in row.forecast_type for row in forecasts)
        bearish = any("BEARISH" in row.forecast_type for row in forecasts)
        positive_price = sum(1 for row in forecasts if row.forecast_value > 0)
        negative_price = sum(1 for row in forecasts if row.forecast_value < 0)
        forecast_score = _clamp01(0.5 + (0.2 if bullish else 0.0) - (0.2 if bearish else 0.0) + ((positive_price - negative_price) * 0.05))
        demand_score = _clamp01(sum(float(row.confidence_score) for row in signals[:5]) / max(len(signals[:5]), 1))
        risk_score = _clamp01(sum(min(float(row.risk_score) / 10.0, 1.0) for row in risks[:3]) / max(len(risks[:3]), 1)) if risks else 0.0
        grading_score = round(_clamp01((forecast_score * 0.6) + (demand_score * 0.4)), 4) if asset_type in {"inventory_copy", "marketplace_listing"} else None
        opportunity_score = round(
            _clamp01((forecast_score * 0.4) + (demand_score * 0.3) + ((1.0 - risk_score) * 0.2) + ((grading_score or 0.0) * 0.1)),
            4,
        )
        row = DealerOpportunityScore(
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            opportunity_score=opportunity_score,
            risk_score=round(risk_score, 4),
            forecast_score=round(forecast_score, 4),
            demand_score=round(demand_score, 4),
            grading_score=grading_score,
            calculated_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return [_opportunity_read(row) for row in created]


def rank_recommendations(rows: list[DealerRecommendationRead]) -> list[DealerRecommendationRead]:
    return sorted(rows, key=lambda row: (-row.priority_score, -row.confidence_score, row.created_at))


def _visible_recommendation_statement(*, owner_user_id: int):
    return select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_user_id)


def _visible_recommendation_row(session: Session, *, owner_user_id: int, recommendation_id: int) -> DealerRecommendation:
    row = session.exec(
        _visible_recommendation_statement(owner_user_id=owner_user_id).where(DealerRecommendation.id == recommendation_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Dealer recommendation not found.")
    return row


def recommendation_detail(session: Session, *, recommendation_id: int) -> DealerRecommendationDetail:
    row = session.get(DealerRecommendation, recommendation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dealer recommendation not found.")
    return DealerRecommendationDetail(
        recommendation=_recommendation_read(session, row),
        evidence=[_evidence_read(item) for item in _evidence_rows(session, recommendation_id=recommendation_id)],
        reviews=[_review_read(item) for item in _review_rows(session, recommendation_id=recommendation_id)],
    )


def get_recommendation_for_owner(session: Session, *, owner_user_id: int, recommendation_id: int) -> DealerRecommendationDetail:
    row = _visible_recommendation_row(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    return recommendation_detail(session, recommendation_id=int(row.id or 0))


def list_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    recommendation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DealerRecommendationListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = _visible_recommendation_statement(owner_user_id=owner_user_id)
    if recommendation_type is not None:
        stmt = stmt.where(DealerRecommendation.recommendation_type == recommendation_type.strip().upper())
    rows = session.exec(
        stmt.order_by(DealerRecommendation.priority_score.desc(), DealerRecommendation.created_at.asc(), DealerRecommendation.id.asc())
    ).all()
    items = [_recommendation_read(session, row) for row in rows]
    if recommendation_status is not None:
        normalized = recommendation_status.strip().upper()
        items = [item for item in items if item.recommendation_status == normalized]
    total = len(items)
    return DealerRecommendationListResponse(items=items[offset : offset + limit], total_items=total, limit=limit, offset=offset)


def list_opportunities(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> DealerOpportunityScoreListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(DealerOpportunityScore)
        .where(DealerOpportunityScore.owner_user_id == owner_user_id)
        .order_by(DealerOpportunityScore.opportunity_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
    ).all()
    items = [_opportunity_read(row) for row in rows]
    return DealerOpportunityScoreListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def list_executions(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> DealerCopilotExecutionListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(DealerCopilotExecution)
        .where(DealerCopilotExecution.owner_user_id == owner_user_id)
        .order_by(DealerCopilotExecution.created_at.desc(), DealerCopilotExecution.id.desc())
    ).all()
    items = [_execution_read(row) for row in rows]
    return DealerCopilotExecutionListResponse(items=items[offset : offset + limit], total_items=len(items), limit=limit, offset=offset)


def append_review(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_status: str,
    review_notes: str | None = None,
) -> DealerRecommendationDetail:
    row = _visible_recommendation_row(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    session.add(
        DealerRecommendationReview(
            recommendation_id=int(row.id or 0),
            review_status=review_status.strip().upper(),
            reviewed_by=reviewed_by.strip(),
            reviewed_at=utc_now(),
            review_notes=(review_notes or "").strip() or None,
        )
    )
    session.commit()
    return get_recommendation_for_owner(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)


def _top_by_type(session: Session, *, owner_user_id: int, recommendation_type: str, limit: int) -> list[DealerRecommendationRead]:
    return list_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation_type=recommendation_type,
        limit=limit,
        offset=0,
    ).items


def build_copilot_summary(session: Session, *, owner_user_id: int) -> DealerCopilotSummaryRead:
    rows = session.exec(_visible_recommendation_statement(owner_user_id=owner_user_id)).all()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    open_count = 0
    for row in rows:
        by_type[row.recommendation_type] = by_type.get(row.recommendation_type, 0) + 1
        reviews = _review_rows(session, recommendation_id=int(row.id or 0))
        status = _display_status(row, reviews)
        by_status[status] = by_status.get(status, 0) + 1
        if status == RECOMMENDATION_STATUS_OPEN:
            open_count += 1
    return DealerCopilotSummaryRead(
        total_recommendations=len(rows),
        open_recommendations=open_count,
        by_type=by_type,
        by_status=by_status,
    )


def build_copilot_dashboard(session: Session, *, owner_user_id: int) -> DealerCopilotDashboardRead:
    return DealerCopilotDashboardRead(
        summary=build_copilot_summary(session, owner_user_id=owner_user_id),
        top_buys=_top_by_type(session, owner_user_id=owner_user_id, recommendation_type="BUY", limit=5),
        top_sells=_top_by_type(session, owner_user_id=owner_user_id, recommendation_type="SELL", limit=5),
        top_holds=_top_by_type(session, owner_user_id=owner_user_id, recommendation_type="HOLD", limit=5),
        top_grades=_top_by_type(session, owner_user_id=owner_user_id, recommendation_type="GRADE", limit=5),
        top_watchlist=_top_by_type(session, owner_user_id=owner_user_id, recommendation_type="WATCH", limit=5),
        opportunities=list_opportunities(session, owner_user_id=owner_user_id, limit=10, offset=0).items,
        executions=list_executions(session, owner_user_id=owner_user_id, limit=10, offset=0).items,
    )


def generate_recommendations(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    from app.services.buy_list_agent import run_buy_list_agent
    from app.services.sell_agent import run_sell_agent
    from app.services.hold_agent import run_hold_agent
    from app.services.grade_candidate_agent import run_grade_candidate_agent
    from app.services.watchlist_agent import run_watchlist_agent

    opportunities = calculate_opportunity_scores(session, owner_user_id=owner_user_id)
    buy = run_buy_list_agent(session, owner_user_id=owner_user_id)
    sell = run_sell_agent(session, owner_user_id=owner_user_id)
    hold = run_hold_agent(session, owner_user_id=owner_user_id)
    grade = run_grade_candidate_agent(session, owner_user_id=owner_user_id)
    watch = run_watchlist_agent(session, owner_user_id=owner_user_id)
    recommendations = rank_recommendations([*buy.recommendations, *sell.recommendations, *hold.recommendations, *grade.recommendations, *watch.recommendations])
    executions = [
        *(buy.executions or []),
        *(sell.executions or []),
        *(hold.executions or []),
        *(grade.executions or []),
        *(watch.executions or []),
    ]
    return DealerCopilotRunResponse(recommendations=recommendations, opportunities=opportunities, executions=executions)
